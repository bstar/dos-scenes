/* DOS Scenes: cooperative real-mode EGA and OPL2 scene runtime. */
#include <dos.h>
#include <bios.h>
#include <conio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include <ctype.h>
#include <errno.h>
#define PLANE 8000
#define PIT_DIV 2131U
#define MUSIC_MAX 60000U
#ifdef DOS_SCENES_EMBEDDED
#include "dos_scenes.h"

unsigned long dsFrames,dsSceneTicks;
unsigned dsError,dsAdlib,dsFault;
#endif
static const char *asset_directory;
static unsigned char far *background, far *frame;
static unsigned char far *song;
static unsigned song_size, song_pos, song_wait;
#define TRACKS 16
static unsigned char far *songs[TRACKS];
static unsigned song_sizes[TRACKS], song_index, song_count;
static unsigned track_changes;
static unsigned played_mask;
static unsigned char opl_regs[256], opl_seen[256];
static unsigned char hw_regs[256];
static volatile unsigned long audio_events, opl_writes;
static volatile unsigned irq_batch_max, irq_caps, audio_fault;
static unsigned long audio_late_max;
static unsigned log_enabled;
static FILE *audio_log;
static const char *asset_name(const char *name) {
    static char path[128];
    if(asset_directory) { sprintf(path,"%s\\%s",asset_directory,name); return path; }
    return name;
}
static unsigned opl_slow,opl_pit_guard=1,opl_pit_timeouts;
static unsigned opl_address_floor=65535U,opl_data_floor=65535U;
static unsigned master_level=28; /* 0=off, 28=original mix, 32=+6 dB. */
/* Shared with the saver through asset_directory; all DOS I/O is foreground. */
static unsigned volume_dirty;
static unsigned long volume_due;
static int read_volume(const char *name,unsigned *level) {
    FILE *f=fopen(asset_name(name),"rb"); char b[32],*end; unsigned n; long v;
    if(!f) return 0;
    n=fread(b,1,sizeof(b)-1,f);
    if(ferror(f) || !feof(f)) { fclose(f); return 0; }
    fclose(f); if(memchr(b,0,n)) return 0; b[n]=0; errno=0; v=strtol(b,&end,10);
    if(end==b || errno || v<0 || v>32) return 0;
    while(*end && isspace((unsigned char)*end)) end++;
    if(*end) return 0;
    *level=(unsigned)v; return 1;
}
static void load_volume(void) {
    unsigned level;
    if(volume_dirty) return; /* Preserve an unsaved setting after an I/O failure. */
    master_level=28;
    if(read_volume("VOLUME.CFG",&level) || read_volume("VOLUME.BAK",&level))
        master_level=level;
}
static int save_volume(void) {
    FILE *f; char cfg[128],bak[128],tmp[128]; int ok,had_old=0;
    if(!volume_dirty) return 1;
    strcpy(cfg,asset_name("VOLUME.CFG")); strcpy(bak,asset_name("VOLUME.BAK"));
    strcpy(tmp,asset_name("VOLSET.TMP"));
    f=fopen(tmp,"wb"); if(!f) return 0;
    ok=fprintf(f,"%u\r\n",master_level)>0;
    if(fclose(f)) ok=0;
    if(!ok) return 0;
    f=fopen(cfg,"rb");
    if(f) {
        fclose(f);
        if(remove(bak) && errno!=ENOENT) return 0;
        if(rename(cfg,bak)) return 0;
        had_old=1;
    }
    if(rename(tmp,cfg)) { if(had_old) rename(bak,cfg); return 0; }
    volume_dirty=0; return 1;
}
static unsigned char op_offsets[9]={0,1,2,8,9,10,16,17,18};
static volatile unsigned long ticks;
static unsigned long audio_due;
static void select_song(unsigned index) {
    unsigned i;
    for(i=0;i<256;i++) { opl_regs[i]=0; opl_seen[i]=0; }
    song_index=index;
    played_mask|=1U<<index;
    song=songs[index]; song_size=song_sizes[index]; song_pos=0;
    song_wait=song_size ? song[0]|((unsigned)song[1]<<8) : 0;
    audio_due=ticks+song_wait;
}
static unsigned long bios_phase;
static volatile int muted;
static int adlib, installed, oldmode;
static unsigned char far *flames, far *sky, far *display_palette, far *moon_sprite;
static unsigned moon_x,moon_y,moon_w,moon_h;
static unsigned fire_w,fire_h,fire_count,frame_ticks=40;
static int fire_x,fire_y,moon_dx=88,moon_dy=80;
static unsigned long moon_duration=2016000UL;
static char scene_name[48]="DOS Scene";
static void (__interrupt __far *oldtimer)(void);
static unsigned pit_latch(void);
#pragma aux pit_latch = \
    "pushf" \
    "cli" \
    "xor al,al" \
    "out 43h,al" \
    "in al,40h" \
    "mov ah,al" \
    "in al,40h" \
    "xchg al,ah" \
    "popf" \
    value [ax] modify exact [ax];
static unsigned opl_wait(unsigned last,unsigned target) {
    unsigned now,delta,elapsed=0,tries;
    for(tries=0;tries<4096;tries++) {
        now=pit_latch();
        /* Channel0 mode3 decrements by two per PIT clock. Its half-cycle
           reload is PIT_DIV while installed, otherwise the BIOS65536. */
        delta=last>=now ? last-now : (unsigned)(last+(installed?PIT_DIV:0U)-now);
        if(delta>=target-elapsed) return elapsed+delta;
        elapsed+=delta; last=now;
    }
    /* A non-advancing/unsupported timer must not hang the machine. Retain
       the classic ISA status-read delays if the optional guard fails. */
    opl_pit_timeouts++; opl_pit_guard=0; return 0;
}
static void opl(unsigned reg, unsigned val) {
    unsigned i,start=0,elapsed;
    outp(0x388,reg);
    if(opl_pit_guard) start=pit_latch();
    for(i=0;i<(opl_slow?12U:6U);i++) inp(0x388);
    if(opl_pit_guard) {
        /*14/68 mode3 counts include margin beyond12/84 OPL clock recovery
          cycles: even with tick quantization, >=5us address and >=27us data. */
        elapsed=opl_wait(start,opl_slow?28U:14U);
        if(elapsed && elapsed<opl_address_floor) opl_address_floor=elapsed;
    }
    outp(0x389,val);
    if(opl_pit_guard) start=pit_latch();
    for(i=0;i<(opl_slow?72U:36U);i++) inp(0x388);
    if(opl_pit_guard) {
        elapsed=opl_wait(start,opl_slow?136U:68U);
        if(elapsed && elapsed<opl_data_floor) opl_data_floor=elapsed;
    }
    hw_regs[reg]=(unsigned char)val; opl_writes++;
}
static void silence(void) {
    unsigned i;
    for(i=0;i<9;i++) opl(0xb0+i,0);
    /* Rhythm voices use BD key bits rather than the melodic B0 key bits. */
    opl(0xbd,0);
    /* Key-off alone can leave a long release, or an RR=0 voice sounding. */
    for(i=0;i<9;i++) {
        opl(0x40+op_offsets[i],63);
        opl(0x43+op_offsets[i],63);
    }
}
static unsigned scaled_level(unsigned reg,unsigned val) {
    unsigned c; int output=0, level;
    if(!master_level) return (val&0xc0)|63;
    for(c=0;c<9;c++) {
        if(reg==0x43+op_offsets[c]) { output=1; break; }
        if(reg==0x40+op_offsets[c]) {
            output=((opl_regs[0xbd]&32) && c>=7) || (opl_regs[0xc0+c]&1);
            break;
        }
    }
    if(!output) return val; /* Leave FM modulation depth/timbre unchanged. */
    level=(val&63)+(28-(int)master_level)*2;
    if(level<0) level=0; if(level>63) level=63;
    return (val&0xc0)|(unsigned)level;
}
static void refresh_channel(unsigned c) {
    unsigned r=0x40+op_offsets[c];
    if(opl_seen[r]) opl(r,scaled_level(r,opl_regs[r]));
    r+=3; if(opl_seen[r]) opl(r,scaled_level(r,opl_regs[r]));
}
static void music_opl(unsigned reg,unsigned val) {
    unsigned old=opl_regs[reg],c;
    opl_regs[reg]=(unsigned char)val; opl_seen[reg]=1;
    if(reg>=0x40 && reg<=0x55) val=scaled_level(reg,val);
    if(!master_level) {
        if(reg>=0xb0 && reg<=0xb8) val&=~32U;
        if(reg==0xbd) val&=~31U;
    }
    opl(reg,val);
    if(master_level!=28) {
        if(reg>=0xc0 && reg<=0xc8) refresh_channel(reg-0xc0);
        if(reg==0xbd && ((old^opl_regs[reg])&32))
            for(c=6;c<9;c++) refresh_channel(c);
    }
}
static void change_volume(int step) {
    unsigned old=master_level,c; int level=(int)master_level+step;
    if(level<0) level=0; if(level>32) level=32;
    master_level=(unsigned)level;
    if(master_level!=old) { volume_dirty=1; volume_due=ticks+280UL; }
    if(!adlib || muted) return;
    for(c=0;c<9;c++) refresh_channel(c);
    if(!old || !master_level) {
        for(c=0;c<9;c++) if(opl_seen[0xb0+c])
            opl(0xb0+c,master_level ? opl_regs[0xb0+c] : opl_regs[0xb0+c]&~32U);
        if(opl_seen[0xbd]) opl(0xbd,master_level ? opl_regs[0xbd] : opl_regs[0xbd]&~31U);
    }
}
static int detect_opl(void) {
    unsigned a,b,start=0; int i;
    opl(4,0x60); opl(4,0x80); a=inp(0x388);
    opl(2,0xff); opl(4,0x21);
    if(opl_pit_guard) start=pit_latch();
    for(i=0;i<200;i++) inp(0x388);
    if(opl_pit_guard) opl_wait(start,210U); /* >80us detection timer wait. */
    b=inp(0x388); opl(4,0x60); opl(4,0x80);
    return (a&0xe0)==0 && (b&0xe0)==0xc0;
}
static unsigned delay_at(unsigned p) { return song[p]|((unsigned)song[p+1]<<8); }
static void audio_poll(void) {
    unsigned count=0;
    unsigned long now,due,late;
    if(!adlib || !song_size || audio_fault) return;
    _disable(); now=ticks; _enable();
    if(adlib && song_size && !audio_fault) {
        while((long)(now-audio_due)>=0 && count++<256) {
            late=now-audio_due; if(late>audio_late_max) audio_late_max=late;
            if(song_pos>song_size-4 || (song_pos&3)) {
                audio_fault=1; silence(); break;
            }
            audio_events++;
            if(!muted) music_opl(song[song_pos+2],song[song_pos+3]);
            song_pos+=4;
            if(song_pos>=song_size) {
                due=audio_due;
                select_song((song_index+1)%song_count);
                audio_due=due+song_wait;
                track_changes++;
            } else audio_due+=delay_at(song_pos);
            _disable(); now=ticks; _enable();
        }
        song_wait=(long)(audio_due-now)>0 ? (unsigned)(audio_due-now) : 0;
        if(count>irq_batch_max) irq_batch_max=count;
        if(!song_wait && count>=256) irq_caps++;
    }
}
static void poll_volume(void) {
    unsigned long now;
    if(!volume_dirty) return;
    _disable(); now=ticks; _enable();
    if((long)(now-volume_due)>=0 && !save_volume()) volume_due=now+5600UL;
}
static void __interrupt __far timer(void) {
    /* No OPL I/O, allocation, file access or playback work in IRQ0. */
    ticks++;
    bios_phase+=PIT_DIV;
    if(bios_phase>=65536UL) { bios_phase-=65536UL; _chain_intr(oldtimer); }
    else outp(0x20,0x20);
}
static void start_timer(void) {
    oldtimer=_dos_getvect(8); _disable(); _dos_setvect(8,timer);
    outp(0x43,0x36); outp(0x40,PIT_DIV&255); outp(0x40,PIT_DIV>>8);
    installed=1; _enable();
}
static void stop_timer(void) {
    if(!installed) return;
    _disable(); outp(0x43,0x36); outp(0x40,0); outp(0x40,0);
    _dos_setvect(8,oldtimer); installed=0; _enable();
}
/* All file I/O and OPL writes are in the foreground. Register values below
   are software copies of writes, not readback from the write-only OPL. */
static void log_audio(const char *reason,unsigned long frames,int key) {
    unsigned long t,events,writes,bios; unsigned track,pos,size,wait,level,mute;
    unsigned batch,caps,fault,source_keys=0,hardware_keys=0,i,seg,off;
    unsigned char levels[18],source_bd,hardware_bd,status,next_reg=0,next_val=0;
    if(!audio_log) return;
    _disable();
    t=ticks; events=audio_events; writes=opl_writes;
    bios=*(volatile unsigned long far*)MK_FP(0x40,0x6c);
    track=song_index+1; pos=song_pos; size=song_size; wait=song_wait;
    level=master_level; mute=muted; batch=irq_batch_max; caps=irq_caps; fault=audio_fault;
    seg=FP_SEG(song); off=FP_OFF(song);
    source_bd=opl_regs[0xbd]; hardware_bd=hw_regs[0xbd];
    status=adlib ? inp(0x388) : 0;
    for(i=0;i<9;i++) {
        if(opl_regs[0xb0+i]&32) source_keys|=1U<<i;
        if(hw_regs[0xb0+i]&32) hardware_keys|=1U<<i;
        levels[i*2]=hw_regs[0x40+op_offsets[i]];
        levels[i*2+1]=hw_regs[0x43+op_offsets[i]];
    }
    if(size>=4 && pos<=size-4) { next_reg=song[pos+2]; next_val=song[pos+3]; }
    _enable();
    fprintf(audio_log,"%s,%lu,%lu,%lu,%lu,%lu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%d",
        reason,t,frames,bios,events,writes,track,pos,size,wait,level,mute,
        source_keys,hardware_keys,source_bd,hardware_bd,status,batch,caps,fault,seg,off,key);
    fprintf(audio_log,",%u,%u",next_reg,next_val);
    fprintf(audio_log,",%lu",audio_late_max);
    for(i=0;i<18;i++) fprintf(audio_log,",%u",levels[i]);
    fprintf(audio_log,",%u,%u,%u,%u,%u",opl_pit_guard,opl_pit_timeouts,opl_address_floor,opl_data_floor,opl_slow);
    fputs("\n",audio_log); fflush(audio_log);
}
static void mode(unsigned n) { union REGS r; r.h.ah=0; r.h.al=n; int86(0x10,&r,&r); }
static void pixel(int x,int y,unsigned c) {
    unsigned off,mask,p; unsigned char far *b;
    if(x<0 || x>=320 || y<0 || y>=200) return;
    off=y*40+(x>>3); mask=0x80>>(x&7);
    for(p=0;p<4;p++) { b=frame+p*PLANE+off; if(c&(1<<p)) *b|=mask; else *b&=~mask; }
}
/* Optional scene detail records; all geometry is supplied by the scene pack. */
static unsigned char far *details;
static unsigned details_size,light_count,route_count,ripple_count,ripple_start;
static unsigned route_start[32];
static unsigned detail_word(unsigned at) { return details[at]|((unsigned)details[at+1]<<8); }
static unsigned background_color(unsigned x,unsigned y) {
    unsigned off=y*40+(x>>3),mask=128>>(x&7),p,c=0;
    for(p=0;p<4;p++) if(background[p*PLANE+off]&mask) c|=1U<<p;
    return c;
}
static void ambience(unsigned long t) {
    unsigned i,at,x,y,c,period,phase,step,cycle,route,n,mask,cutoff;
    unsigned long travel,journey;
    for(i=0,at=10;i<light_count;i++,at+=12) {
        x=detail_word(at);y=detail_word(at+2);period=detail_word(at+4);
        phase=(unsigned)((t+detail_word(at+6))%period);
        if(phase<detail_word(at+8)) pixel(x,y,details[at+10]);
    }
    audio_poll();
    for(i=0;i<route_count;i++) {
        at=route_start[i];n=detail_word(at);cycle=n+detail_word(at+4);
        travel=t/detail_word(at+2)+detail_word(at+6);
        journey=travel/cycle;step=(unsigned)(travel%cycle);
        if(step>=n) continue;
        route=(unsigned)(journey*25173UL+detail_word(at+8)*13849UL+173UL);
        route^=route>>7;route=(unsigned)(route*40503U);route^=route>>9;
        if(route&1U) step=n-1U-step;
        cutoff=detail_word(at+10);mask=detail_word(at+14);
        x=detail_word(at+16+step*4);y=detail_word(at+18+step*4);
        c=background_color(x,y);
        if(mask&(1U<<c)) pixel(x,y,details[at+(y>cutoff?12:13)]);
        if(y>cutoff) {
            c=background_color(x,y-1);
            if(mask&(1U<<c)) pixel(x,y-1,details[at+13]);
        }
        audio_poll();
    }
    for(i=0,at=ripple_start;i<ripple_count;i++,at+=18) {
        period=detail_word(at+10);
        phase=(unsigned)((t/detail_word(at+6)+detail_word(at+8))%period);
        if(phase%detail_word(at+12)>=detail_word(at+14)) continue;
        x=detail_word(at)+phase%detail_word(at+4);y=detail_word(at+2);
        c=background_color(x,y);
        if(c==details[at+16] || c==details[at+17])
            pixel(x,y,c==details[at+16]?details[at+17]:details[at+16]);
    }
}
static void present(unsigned page) {
    unsigned p,chunk,base=page*8192; union REGS r;
    for(p=0;p<4;p++) {
        outp(0x3c4,2); outp(0x3c5,1<<p);
        for(chunk=0;chunk<PLANE;chunk+=2000) {
            _fmemcpy((void far*)MK_FP(0xa000,base+chunk),frame+p*PLANE+chunk,2000);
            audio_poll();
        }
    }
    outp(0x3c4,2); outp(0x3c5,15);
    /* Bounded retrace wait also works without depending on VGA registers. */
    { unsigned n=65535; while((inp(0x3da)&8) && --n) { if(!(n&63)) audio_poll(); }
      n=65535; while(!(inp(0x3da)&8) && --n) { if(!(n&63)) audio_poll(); } }
    r.h.ah=5; r.h.al=page; int86(0x10,&r,&r);
}
static int read_asset(char *name,unsigned char far **buf,unsigned expected) {
    FILE *f=fopen(asset_name(name),"rb"); long n;
    if(!f) return 0; fseek(f,0,SEEK_END); n=ftell(f); rewind(f);
    if(n<=0 || n>60000L || (expected && n!=expected)) { fclose(f); return 0; }
    *buf=_fmalloc((unsigned)n);
    if(!*buf) { fclose(f); return 0; }
    if(fread(*buf,1,(unsigned)n,f)!=(unsigned)n) {
        fclose(f); _ffree(*buf); *buf=0; return 0;
    }
    fclose(f); return (int)n;
}
static void fire(unsigned long t) {
    unsigned x,y,c,offset;
    if(!flames) return;
    offset=6+(unsigned)(t%fire_count)*fire_w*fire_h;
    for(y=0;y<fire_h;y++) { audio_poll(); for(x=0;x<fire_w;x++) {
        c=flames[offset+y*fire_w+x]; pixel(fire_x+x,fire_y+y,c);
    } }
}
static int is_sky(int x,int y) {
    if(x<0 || x>=320 || y<0 || y>=200) return 0;
    return sky && (sky[y*40+(x>>3)]&(0x80>>(x&7)));
}
/* Projected setting arc: one hour from the source position to beyond the
   right edge. Clamp at the horizon; the moon does not jump back into view. */
static unsigned moon_arc[33][2]={
    {0,0},
    {13,0},
    {25,1},
    {38,3},
    {50,5},
    {62,8},
    {74,11},
    {86,15},
    {98,19},
    {109,25},
    {121,30},
    {132,36},
    {142,43},
    {152,50},
    {162,58},
    {172,66},
    {181,75},
    {190,84},
    {198,94},
    {206,104},
    {213,114},
    {220,124},
    {226,135},
    {231,147},
    {237,158},
    {241,170},
    {245,182},
    {248,194},
    {251,206},
    {253,218},
    {255,231},
    {256,243},
    {256,256},
};
static void draw_moon(unsigned long now) {
    unsigned phase,part,x,y,c; int left,top;
    if(!moon_sprite) return;
    if(now>=moon_duration) return;
    phase=(unsigned)(now*32UL/moon_duration);
    part=(unsigned)((now*32UL%moon_duration)*3600UL/moon_duration);
    left=(int)moon_x+(int)((long)moon_dx*(long)(moon_arc[phase][0]+(unsigned long)(moon_arc[phase+1][0]-moon_arc[phase][0])*part/3600UL)/256L);
    top=(int)moon_y+(int)((long)moon_dy*(long)(moon_arc[phase][1]+(unsigned long)(moon_arc[phase+1][1]-moon_arc[phase][1])*part/3600UL)/256L);
    for(y=0;y<moon_h;y++) for(x=0;x<moon_w;x++) {
        c=moon_sprite[8+y*moon_w+x];
        if(c!=255 && is_sky(left+x,top+y)) pixel(left+x,top+y,c);
    }
}
/* Video-derived keyframes. Each sequence has its own measured repeat period. */
static unsigned char far *meteor[2];
static unsigned meteor_size[2];
static unsigned word_at(unsigned char far *b,unsigned n) { return b[n]|((unsigned)b[n+1]<<8); }
static void stars(unsigned long now) {
    unsigned seq,i,n,period,phase,at,off,w,h,hold,x,y,c; int px,py;
    for(seq=0;seq<2;seq++) {
        unsigned char far *b=meteor[seq];
        if(!b) continue;
        n=word_at(b,0);period=word_at(b,2);phase=word_at(b,4);
        at=(unsigned)(now%period); if(at<phase) continue; at-=phase; off=6;
        for(i=0;i<n;i++) {
            px=(int)word_at(b,off);py=(int)word_at(b,off+2);
            w=word_at(b,off+4);h=word_at(b,off+6);hold=word_at(b,off+8);off+=10;
            if(at<hold) {
                for(y=0;y<h;y++) { audio_poll(); for(x=0;x<w;x++) {
                    c=b[off+y*w+x];
                    if(c!=255 && is_sky(px+x,py+y)) pixel(px+x,py+y,c);
                } }
                break;
            }
            at-=hold;off+=w*h;
        }
    }
}
static void load_meteor(unsigned n,char *name) {
    unsigned off=6,i,count,w,h,hold;
    meteor_size[n]=read_asset(name,&meteor[n],0);
    if(!meteor[n]) return;
    if(meteor_size[n]<6 || !word_at(meteor[n],2)) goto bad;
    count=word_at(meteor[n],0);
    if(count>64) goto bad;
    for(i=0;i<count;i++) {
        if((unsigned long)off+10>meteor_size[n]) goto bad;
        w=word_at(meteor[n],off+4);h=word_at(meteor[n],off+6);hold=word_at(meteor[n],off+8);
        if(!w || !h || w>320 || h>100 || !hold || (unsigned long)off+10+(unsigned long)w*h>meteor_size[n]) goto bad;
        off+=10+w*h;
    }
    if(off==meteor_size[n]) return;
 bad: _ffree(meteor[n]);meteor[n]=0;
}
/* Cloud mask is palette-indexed, 255 transparent, with a 4-byte LE width/height header. */
static unsigned char far *cloud;
static unsigned cw,ch;
static unsigned char far *cloud_shifted[8];
static int cloud_origin;
static unsigned cloud_top;
static unsigned cloud_spacing=870,cloud_mul=41,cloud_div=6244;
static unsigned long cloud_cycle=132508UL;
static unsigned cloud_bytes;
static void prepare_cloud(void) {
    unsigned shift,x,y,p,bit,offset,c; unsigned char far *dst;
    if(!cloud) return;
    cloud_bytes=(cw+14)/8;
    if((unsigned long)cloud_bytes*ch*5>60000UL) return;
    for(shift=0;shift<8;shift++) {
        cloud_shifted[shift]=_fmalloc(cloud_bytes*ch*5);
        if(!cloud_shifted[shift]) return;
        _fmemset(cloud_shifted[shift],0,cloud_bytes*ch*5);
    }
    for(shift=0;shift<8;shift++) for(y=0;y<ch;y++) for(x=0;x<cw;x++) {
        c=cloud[8+y*cw+x]; if(c==255) continue;
        offset=y*cloud_bytes+(x+shift)/8;
        bit=128>>((x+shift)&7); dst=cloud_shifted[shift]+offset;
        *dst|=bit;
        for(p=0;p<4;p++) if(c&(1<<p)) dst[(p+1)*ch*cloud_bytes]|=bit;
    }
}
static void clouds(unsigned long t) {
    int left,bx,screenx; unsigned shift,y,x,p,off,mask,src;
    if(!cloud_shifted[7] || !sky) return;
    /* Motion is measured on the registered native5x grid, independent of frame rate. */
    left=(int)((cloud_origin+(int)cloud_spacing-(int)(((t%cloud_cycle)*cloud_mul)/cloud_div))%(int)cloud_spacing);
    if(left>=320) left-=cloud_spacing;
    shift=(unsigned)left&7; bx=(left-(int)shift)/8;
    for(y=0;y<ch;y++) { audio_poll(); for(x=0;x<cloud_bytes;x++) {
        screenx=bx+x; if(screenx<0 || screenx>=40) continue;
        off=(cloud_top+y)*40+screenx;
        src=y*cloud_bytes+x;
        mask=cloud_shifted[shift][src]&sky[off];
        if(mask) for(p=0;p<4;p++) {
            unsigned char far *d=frame+p*PLANE+off;
            *d=(*d&~mask)|(cloud_shifted[shift][src+(p+1)*ch*cloud_bytes]&mask);
        }
    } }
}
static void free_scene(void) {
    unsigned i;
    save_volume();
    if(background) { _ffree(background); background=0; }
    if(frame) { _ffree(frame); frame=0; }
    if(cloud) { _ffree(cloud); cloud=0; }
    for(i=0;i<TRACKS;i++) if(songs[i]) { _ffree(songs[i]); songs[i]=0; }
    for(i=0;i<8;i++) if(cloud_shifted[i]) { _ffree(cloud_shifted[i]); cloud_shifted[i]=0; }
    for(i=0;i<2;i++) if(meteor[i]) { _ffree(meteor[i]); meteor[i]=0; }
    if(display_palette) { _ffree(display_palette); display_palette=0; }
    if(flames) { _ffree(flames); flames=0; }
    if(sky) { _ffree(sky); sky=0; }
    if(details) { _ffree(details);details=0; }
    light_count=route_count=ripple_count=0;
    if(moon_sprite) { _ffree(moon_sprite); moon_sprite=0; }
    song=0; song_count=0; song_size=0;
}
static void load_options(void) {
    FILE *f=fopen(asset_name("SCENE.CFG"),"r");char line[128],key[32],value[80];long n;
    fire_x=fire_y=0;frame_ticks=40;moon_dx=88;moon_dy=80;moon_duration=2016000UL;
    strcpy(scene_name,"DOS Scene");
    if(!f) return;
    while(fgets(line,sizeof(line),f)) {
        if(sscanf(line,"%31s %79[^\r\n]",key,value)!=2 || key[0]=='#') continue;
        n=atol(value);
        if(!stricmp(key,"NAME")) { strncpy(scene_name,value,sizeof(scene_name)-1);scene_name[sizeof(scene_name)-1]=0; }
        else if(!stricmp(key,"FIRE_X") && n>=-64 && n<320) fire_x=(int)n;
        else if(!stricmp(key,"FIRE_Y") && n>=-64 && n<200) fire_y=(int)n;
        else if(!stricmp(key,"FRAME_TICKS") && n>=20 && n<=560) frame_ticks=(unsigned)n;
        else if(!stricmp(key,"MOON_SECONDS") && n>=1 && n<=86400L) moon_duration=n*560UL;
        else if(!stricmp(key,"MOON_DX") && n>=-640 && n<=640) moon_dx=(int)n;
        else if(!stricmp(key,"MOON_DY") && n>=-200 && n<=200) moon_dy=(int)n;
    }
    fclose(f);
}
static int prepare_details(void) {
    unsigned i,j,at,n,x,y;
    details_size=read_asset("DETAILS.BIN",&details,0);
    if(!details) return 1;
    if(details_size<10 || _fmemcmp(details,"DSD1",4)) return 0;
    light_count=detail_word(4);route_count=detail_word(6);ripple_count=detail_word(8);
    if(light_count>128 || route_count>32 || ripple_count>128) return 0;
    at=10;
    for(i=0;i<light_count;i++,at+=12) {
        if((unsigned long)at+12>details_size || detail_word(at)>=320 || detail_word(at+2)>=200 ||
           !detail_word(at+4) || detail_word(at+8)>detail_word(at+4) || details[at+10]>15) return 0;
    }
    for(i=0;i<route_count;i++) {
        if((unsigned long)at+16>details_size) return 0;
        route_start[i]=at;n=detail_word(at);
        if(n<2 || n>4096 || !detail_word(at+2) || (unsigned long)n+detail_word(at+4)>65535UL ||
           detail_word(at+10)>200 || details[at+12]>15 || details[at+13]>15 ||
           (unsigned long)at+16+(unsigned long)n*4>details_size) return 0;
        for(j=0;j<n;j++) {
            x=detail_word(at+16+j*4);y=detail_word(at+18+j*4);
            if(x>=320 || y>=200) return 0;
        }
        at+=16+n*4;
    }
    ripple_start=at;
    for(i=0;i<ripple_count;i++,at+=18) {
        if((unsigned long)at+18>details_size || detail_word(at)>=320 || detail_word(at+2)>=200 ||
           !detail_word(at+4) || detail_word(at+4)>320-detail_word(at) || !detail_word(at+6) ||
           !detail_word(at+10) || !detail_word(at+12) || detail_word(at+14)>detail_word(at+12) ||
           details[at+16]>15 || details[at+17]>15) return 0;
    }
    return at==details_size;
}
static int load_playlist(void) {
    FILE *f=fopen(asset_name("PLAYLIST.CFG"),"r");char line[80],name[13],*p;unsigned size;
    if(!f) return 1;
    while(fgets(line,sizeof(line),f)) {
        if(sscanf(line,"%12s",name)!=1 || name[0]=='#') continue;
        if(song_count>=TRACKS) { fclose(f);return 0; }
        for(p=name;*p;p++) if(!isalnum((unsigned char)*p) && *p!='.' && *p!='_') { fclose(f);return 0; }
        size=read_asset(name,&songs[song_count],0);
        if(!size || size%4) { fclose(f);return 0; }
        song_sizes[song_count++]=size;
    }
    fclose(f);return 1;
}
static int load_scene(unsigned start_track) {
    int got,legacy=0;
    load_volume();load_options();
    cloud_spacing=870;cloud_mul=41;cloud_div=6244;cloud_cycle=132508UL;
    if(!read_asset("SCENE.EGA",&background,32000)) {
        if(!read_asset("ISLAND.EGA",&background,32000)) return 0;
        legacy=1;
    }
    got=read_asset("MOON.BIN",&moon_sprite,0);
    if(got>=8) {
        moon_x=word_at(moon_sprite,0);moon_y=word_at(moon_sprite,2);
        moon_w=word_at(moon_sprite,4);moon_h=word_at(moon_sprite,6);
        if(!moon_w || !moon_h || moon_w>64 || moon_h>64 ||
           8UL+(unsigned long)moon_w*moon_h!=(unsigned)got) {
            _ffree(moon_sprite);moon_sprite=0;
        }
    } else if(moon_sprite) { _ffree(moon_sprite);moon_sprite=0; }
    if(moon_sprite && legacy) {
        unsigned char far *clean=0;
        if(read_asset("ORIGINAL.EGA",&clean,32000)) { _ffree(background);background=clean; }
        else { _ffree(moon_sprite);moon_sprite=0; }
    }
    frame=_fmalloc(32000); if(!frame) return 0;
    got=read_asset("CLOUD.BIN",&cloud,0);
    if(got>=8) { cloud_origin=(int)word_at(cloud,4);cloud_top=word_at(cloud,6);cw=cloud[0]|((unsigned)cloud[1]<<8); ch=cloud[2]|((unsigned)cloud[3]<<8);
        if(!cw || cw>2000 || !ch || ch>100 || cloud_top+ch>200 || (unsigned long)cw*ch+8!=(unsigned)got) { _ffree(cloud); cloud=0; }
    } else if(cloud) { _ffree(cloud); cloud=0; }
    read_asset("SKY.MSK",&sky,8000);
    got=read_asset("FIRE.BIN",&flames,0);
    if(flames) {
        if(got<6) { _ffree(flames);flames=0; }
        else {
            fire_w=word_at(flames,0);fire_h=word_at(flames,2);fire_count=word_at(flames,4);
            if(!fire_w || !fire_h || !fire_count || fire_w>64 || fire_h>64 || fire_count>64 ||
               6UL+(unsigned long)fire_w*fire_h*fire_count!=(unsigned)got) { _ffree(flames);flames=0; }
        }
    }
    read_asset("PALETTE.BIN",&display_palette,16);
    {
        unsigned char far *motion=0;
        if(read_asset("CLOUD.MOT",&motion,10)) {
            unsigned spacing=word_at(motion,0),mul=word_at(motion,2),div=word_at(motion,4);
            unsigned long cycle=(unsigned long)word_at(motion,6)|((unsigned long)word_at(motion,8)<<16);
            if(spacing>=320 && spacing<=2000 && mul && div && cycle && cycle<1000000UL && (unsigned long)mul<=4000000000UL/cycle) {
                cloud_spacing=spacing;cloud_mul=mul;cloud_div=div;cloud_cycle=cycle;
            }
            _ffree(motion);
        }
    }
    prepare_cloud();
    if(!prepare_details()) return 0;
    if(cloud && cloud_shifted[7]) { _ffree(cloud); cloud=0; }
    load_meteor(0,"STAR1.BIN");load_meteor(1,"STAR2.BIN");
    if(!load_playlist()) return 0;
    if(song_count) select_song((start_track>=1 && start_track<=song_count)?start_track-1:0);
    return 1;
}
#ifndef DOS_SCENES_EMBEDDED
int main(int argc,char **argv) {
    union REGS r; unsigned page=1,start_track=1; unsigned long last=0,now=0,frames=0,limit=0,bios_start,bios_end,scene_offset=0,log_tick=0; int key,i,dump=0;
    for(i=1;i<argc;i++) {
        if(!stricmp(argv[i],"/DUMP")) dump=1;
        else if(!stricmp(argv[i],"/LOG")) log_enabled=1;
        else if(!stricmp(argv[i],"/SLOWOPL")) opl_slow=1;
        else if(!stricmp(argv[i],"/SILENT")) muted=1;
        else if(!strnicmp(argv[i],"/TRACK=",7)) start_track=(unsigned)atoi(argv[i]+7);
        else if(!strnicmp(argv[i],"/AT=",4)) scene_offset=atol(argv[i]+4)*560UL;
        else if(!strnicmp(argv[i],"/FRAMES=",8)) limit=atol(argv[i]+8);
        else if(argv[i][0]!='/' && !asset_directory && strlen(argv[i])<=110) asset_directory=argv[i];
        else { puts("SCENE [directory] [/SILENT] [/FRAMES=n] [/LOG] [/SLOWOPL]\nEsc: exit  M: restart/toggle audio  N: next song  +/-: volume\nWith /LOG, L marks an audio problem in SCENE.LOG."); return 0; }
    }
    if(!load_scene(start_track)) { free_scene(); puts("Missing scene assets or insufficient memory."); return 1; }
    r.h.ah=0x12; r.h.bl=0x10; int86(0x10,&r,&r);
    if(r.h.bl==0x10 || r.h.bl<3) { puts("256 KB EGA or VGA required."); return 1; }
    r.h.ah=0x0f; int86(0x10,&r,&r); oldmode=r.h.al;
    adlib=detect_opl(); if(adlib) { silence(); opl(1,0x20); }
    if(log_enabled) {
        audio_log=fopen(asset_name("SCENE.LOG"),"a");
        if(!audio_log) { puts("Cannot open SCENE.LOG."); return 1; }
        fprintf(audio_log,"RUN,AUDLOG4,service=foreground,keyboard=bios,pit_guard=%u,slow_opl=%u,pit_div=%u,adlib=%d,tracks=%u\n",opl_pit_guard,opl_slow,PIT_DIV,adlib,song_count);
        for(i=0;i<song_count;i++) fprintf(audio_log,"TRACK,%u,bytes=%u,seg=%u,off=%u\n",i+1,song_sizes[i],FP_SEG(songs[i]),FP_OFF(songs[i]));
        fputs("reason,tick,frame,bios,events,writes,track,pos,size,wait,volume,muted,source_keys,written_keys,source_bd,written_bd,status,batch_max,cap_hits,fault,seg,off,key,next_reg,next_val,late_max,tl0m,tl0c,tl1m,tl1c,tl2m,tl2c,tl3m,tl3c,tl4m,tl4c,tl5m,tl5c,tl6m,tl6c,tl7m,tl7c,tl8m,tl8c,pit_guard,pit_timeouts,addr_floor,data_floor,slow_opl\n",audio_log);
        fflush(audio_log);
    }
    mode(0x0d);
    if(display_palette) for(i=0;i<16;i++) { r.h.ah=0x10;r.h.al=0;r.h.bl=i;r.h.bh=display_palette[i];int86(0x10,&r,&r); }
    _disable(); bios_start=*(volatile unsigned long far*)MK_FP(0x40,0x6c); _enable();
    start_timer();
    log_audio("START",0,0);
    while(!limit || frames<limit) {
        audio_poll(); poll_volume();
        if(_bios_keybrd(_KEYBRD_READY)) {
            key=_bios_keybrd(_KEYBRD_READ)&255;
            if(key==27) { log_audio("ESC",frames,key); break; }
            if(key=='m'||key=='M') { muted=!muted; if(adlib) silence(); if(song_count) select_song(song_index); }
            if(key=='+' || key=='=' || key=='-' || key=='_') {
                change_volume((key=='+' || key=='=')?1:-1);
            }
            if((key=='n'||key=='N') && song_count) {
                if(adlib) silence();
                select_song((song_index+1)%song_count); track_changes++;
            }
            log_audio((key=='l'||key=='L')?"MARK":"KEY",frames,key);
        }
        _disable(); now=ticks; _enable();
        if(now-last<frame_ticks) continue; last=now;
        for(i=0;i<4;i++) { _fmemcpy(frame+i*PLANE,background+i*PLANE,PLANE); audio_poll(); }
        draw_moon(now+scene_offset); clouds(now+scene_offset); fire(frames); stars(now+scene_offset); ambience(now+scene_offset);
        present(page); page^=1; frames++;
        if(audio_log && now-log_tick>=560UL) { log_tick=now; log_audio("SAMPLE",frames,0); }
    }
    stop_timer();
    _disable(); bios_end=*(volatile unsigned long far*)MK_FP(0x40,0x6c); _enable();
    log_audio("STOP",frames,0);
    if(adlib) silence();
    log_audio("QUIET",frames,0);
    if(audio_log) { fclose(audio_log); audio_log=0; }
    if(dump) {
        FILE *f=fopen(asset_name("LAST.EGA"),"wb"); unsigned plane,base=(page^1)*8192;
        unsigned char *tmp=malloc(PLANE);
        if(f && tmp) for(plane=0;plane<4;plane++) {
            outp(0x3ce,4); outp(0x3cf,plane);
            _fmemcpy(tmp,(void far*)MK_FP(0xa000,base),PLANE);
            fwrite(tmp,1,PLANE,f);
        }
        if(f) fclose(f); if(tmp) free(tmp);
    }
    mode(oldmode);
    printf("Rendered %lu frames in %lu timer ticks.\n",frames,ticks);
    printf("Scene ticks: %lu\n",now+scene_offset);
    printf("BIOS ticks: %lu; expected: %lu\n",bios_end-bios_start,(ticks*PIT_DIV)/65536UL);
    printf("AdLib: %s; OPL bytes: %u\n",adlib?"present":"absent",song_size);
    printf("Playlist: %u tracks; current: %u; track changes: %u\n",song_count,song_count?song_index+1:0,track_changes);
    printf("Played track mask: %u\n",played_mask);
    free_scene();
    return 0;
}

#else
/* Embedded foreground lifecycle: packet polling runs between calls to Step.
   No spawning, cwd changes, input hooks or resident installation. */
static unsigned saver_page;
static unsigned long saver_last;
int dsBegin(const char *directory) {
    union REGS r; unsigned i;
    if(installed || (directory && strlen(directory)>110)) { dsError=1;return 0; }
    dsError=0; dsFrames=0; dsSceneTicks=0; dsFault=0; dsAdlib=0;
    ticks=0; volume_due=280UL; bios_phase=0; audio_due=0; audio_events=0; opl_writes=0;
    irq_batch_max=0; irq_caps=0; audio_fault=0; audio_late_max=0;
    track_changes=0; played_mask=0; opl_pit_guard=1; opl_pit_timeouts=0;
    opl_address_floor=65535U; opl_data_floor=65535U;
    asset_directory=directory;
    if(!load_scene(1)) { free_scene(); dsError=1; return 0; }
    r.h.ah=0x0f; int86(0x10,&r,&r); oldmode=r.h.al;
    adlib=detect_opl(); dsAdlib=adlib;
    if(adlib) { silence(); opl(1,0x20); }
    mode(0x0d);
    if(display_palette) for(i=0;i<16;i++) {
        r.h.ah=0x10; r.h.al=0; r.h.bl=i; r.h.bh=display_palette[i]; int86(0x10,&r,&r);
    }
    saver_page=1; saver_last=0;
    start_timer();
    return 1;
}
void dsStep(void) {
    unsigned i; unsigned long now;
    if(!installed) return;
    audio_poll(); poll_volume();
    _disable(); now=ticks; _enable();
    if(now-saver_last<frame_ticks) return;
    saver_last=now;
    for(i=0;i<4;i++) { _fmemcpy(frame+i*PLANE,background+i*PLANE,PLANE); audio_poll(); }
    draw_moon(now); clouds(now); fire(dsFrames); stars(now); ambience(now);
    present(saver_page); saver_page^=1; dsFrames++; dsSceneTicks=now; dsFault=audio_fault;
}
void dsEnd(void) {
    if(installed) {
        stop_timer(); if(adlib) silence(); mode(oldmode);
    }
    free_scene();
}
unsigned dsGetVolume(void) { return master_level; }
int dsKey(unsigned key) {
    if(!installed) return 0;
    key&=255;
    if(key=='+' || key=='=' || key=='-' || key=='_') {
        change_volume((key=='+' || key=='=')?1:-1); return 1;
    }
    if(key=='m' || key=='M') {
        muted=!muted; if(adlib) silence(); if(song_count) select_song(song_index); return 1;
    }
    if((key=='n' || key=='N') && song_count) {
        if(adlib) silence(); select_song((song_index+1)%song_count); track_changes++; return 1;
    }
    return 0;
}
#endif
