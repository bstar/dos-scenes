/* DOS Scenes resident launcher. Original code, MIT license.
   Hardware IRQs only record requests. Rendering and DOS work run at INT28. */
#include <dos.h>
#include <i86.h>
#include <bios.h>
#include <conio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include "dos_scenes.h"
typedef void (__interrupt __far *Handler)(void);
static Handler previous_clock,previous_keyboard,previous_idle,previous_mux;
static volatile unsigned char far *in_dos,*critical_error;
static char scene_directory[112];
struct Resident {
    unsigned enabled,pending,busy,timeout,multiplex,last_error,psp,paragraphs;
    unsigned long idle_ticks,activations,last_frames;
};
static struct Resident __near resident;
unsigned short __near ds_saved_ss,ds_saved_sp;
unsigned char __near ds_private_stack[8192];
static unsigned char video_state[4096],font_bytes[8192];
static unsigned short text_cells[2000];
static unsigned cursor_shape,cursor_position;
extern void __cdecl ds_private_call(void);
static unsigned get_psp(void) { union REGS r;r.h.ah=0x51;int86(0x21,&r,&r);return r.x.bx; }
static void set_psp(unsigned psp) { union REGS r;r.h.ah=0x50;r.x.bx=psp;int86(0x21,&r,&r); }
static void far *get_dta(void) {
    union REGS r;struct SREGS s;segread(&s);r.h.ah=0x2f;int86x(0x21,&r,&r,&s);return MK_FP(s.es,r.x.bx);
}
static void set_dta(void far *p) {
    union REGS r;struct SREGS s;segread(&s);s.ds=FP_SEG(p);r.h.ah=0x1a;r.x.dx=FP_OFF(p);int86x(0x21,&r,&r,&s);
}
static unsigned indexed_read(unsigned port,unsigned index) { outp(port,index);return inp(port+1); }
static void indexed_write(unsigned port,unsigned index,unsigned value) { outp(port,index);outp(port+1,value); }
static void font_transfer(int restore) {
    unsigned ports[5]={0x3c4,0x3c4,0x3ce,0x3ce,0x3ce};
    unsigned indices[5]={2,4,4,5,6},values[5],i;
    unsigned seq=inp(0x3c4),gc=inp(0x3ce);
    for(i=0;i<5;i++)values[i]=indexed_read(ports[i],indices[i]);
    indexed_write(0x3c4,2,4);indexed_write(0x3c4,4,6);
    indexed_write(0x3ce,4,2);indexed_write(0x3ce,5,0);indexed_write(0x3ce,6,4);
    if(restore)_fmemcpy(MK_FP(0xa000,0),font_bytes,8192);
    else _fmemcpy(font_bytes,MK_FP(0xa000,0),8192);
    for(i=0;i<5;i++)indexed_write(ports[i],indices[i],values[i]);
    outp(0x3c4,seq);outp(0x3ce,gc);
}
static int video_save(void) {
    union REGS r;struct SREGS s;unsigned seq,map;
    if(*(unsigned char far *)MK_FP(0x40,0x49)!=3 ||
       *(unsigned short far *)MK_FP(0x40,0x4a)!=80 ||
       *(unsigned char far *)MK_FP(0x40,0x84)!=24 ||
       *(unsigned char far *)MK_FP(0x40,0x62)!=0)return 0;
    r.x.ax=0x1a00;int86(0x10,&r,&r);if(r.h.al!=0x1a || (r.h.bl!=7 && r.h.bl!=8))return 0;
    seq=inp(0x3c4);map=indexed_read(0x3c4,3);outp(0x3c4,seq);if(map)return 0;
    r.x.ax=0x1c00;r.x.cx=7;int86(0x10,&r,&r);if(r.h.al!=0x1c || r.x.bx>64)return 0;
    segread(&s);s.es=FP_SEG(video_state);r.x.ax=0x1c01;r.x.cx=7;r.x.bx=FP_OFF(video_state);int86x(0x10,&r,&r,&s);
    if(r.h.al!=0x1c)return 0;
    font_transfer(0);_fmemcpy(text_cells,MK_FP(0xb800,0),4000);
    r.h.ah=3;r.h.bh=0;int86(0x10,&r,&r);cursor_shape=r.x.cx;cursor_position=r.x.dx;return 1;
}
static void video_restore(void) {
    union REGS r;struct SREGS s;
    r.x.ax=3;int86(0x10,&r,&r);font_transfer(1);_fmemcpy(MK_FP(0xb800,0),text_cells,4000);
    segread(&s);s.es=FP_SEG(video_state);r.x.ax=0x1c02;r.x.cx=7;r.x.bx=FP_OFF(video_state);int86x(0x10,&r,&r,&s);
    r.h.ah=1;r.x.cx=cursor_shape;int86(0x10,&r,&r);
    r.h.ah=2;r.h.bh=0;r.x.dx=cursor_position;int86(0x10,&r,&r);
}
static void __interrupt __far ignore_break(void) { }
static void __interrupt __far fail_critical(union INTPACK r) { r.h.al=3; }
void __cdecl ds_resident_run(void) {
    unsigned caller=get_psp(),key;void far *dta=get_dta();
    Handler old_break=_dos_getvect(0x23),old_critical=_dos_getvect(0x24);
    set_psp(resident.psp);set_dta(MK_FP(resident.psp,0x80));resident.last_error=0;
    _dos_setvect(0x23,ignore_break);_dos_setvect(0x24,(Handler)fail_critical);
    if(video_save()) {
        if(dsBegin(scene_directory)) {
            resident.activations++;
            for(;;) {
                if(_bios_keybrd(_KEYBRD_READY)) {
                    key=_bios_keybrd(_KEYBRD_READ);
                    if(!dsKey(key))break;
                }
                dsStep();
            }
            resident.last_frames=dsFrames;dsEnd();
        } else resident.last_error=1;
        video_restore();
    } else resident.last_error=2;
    _fheapshrink();_dos_setvect(0x23,old_break);_dos_setvect(0x24,old_critical);
    set_dta(dta);set_psp(caller);
}
static void __interrupt __far clock_handler(void) {
    if(!resident.busy && resident.enabled && resident.timeout) {
        resident.idle_ticks++;
        if(resident.idle_ticks>=(unsigned long)resident.timeout*182UL/10UL && !resident.pending)resident.pending=2;
    }
    _chain_intr(previous_clock);
}
static void __interrupt __far keyboard_handler(void) {
    unsigned before=*(unsigned short far *)MK_FP(0x40,0x1c),after,word;
    previous_keyboard();resident.idle_ticks=0;if(resident.pending==2)resident.pending=0;
    after=*(unsigned short far *)MK_FP(0x40,0x1c);
    if(after!=before && !resident.busy && resident.enabled) {
        word=*(unsigned short far *)MK_FP(0x40,before);
        if((word>>8)==0x1f && (*(unsigned char far *)MK_FP(0x40,0x17)&12)==12) {
            *(unsigned short far *)MK_FP(0x40,0x1c)=before;resident.pending=1;
        }
    }
}
static void __interrupt __far idle_handler(void) {
    previous_idle();
    _disable();
    if(resident.enabled && resident.pending && !resident.busy && *in_dos<=1 && !*critical_error) {
        resident.busy=1;resident.pending=0;_enable();ds_private_call();
        _disable();resident.busy=0;resident.idle_ticks=0;
    }
    _enable();
}
static void __interrupt __far mux_handler(union INTPACK r) {
    if(r.h.ah!=resident.multiplex)_chain_intr(previous_mux);
    if(r.h.al==0) {
        r.h.al=255;r.w.bx=0x5343;r.w.cx=0x4e45;r.w.dx=1;
        r.w.es=FP_SEG(&resident);r.w.di=FP_OFF(&resident);
    } else if(r.h.al==1) {resident.enabled=1;resident.idle_ticks=0;}
    else if(r.h.al==2) {resident.enabled=0;resident.pending=0;}
    else if(r.h.al==3 && resident.enabled)resident.pending=1;
}
static int find_resident(unsigned *free_id,struct Resident far **found) {
    union REGS r;struct SREGS s;unsigned id;
    *free_id=0;*found=0;
    for(id=0xc0;id<=0xff;id++) {
        memset(&r,0,sizeof(r));segread(&s);r.x.ax=id<<8;int86x(0x2f,&r,&r,&s);
        if(r.h.al==0 && !*free_id)*free_id=id;
        if(r.h.al==255 && r.x.bx==0x5343 && r.x.cx==0x4e45) {
            *found=(struct Resident far *)MK_FP(s.es,r.x.di);return id;
        }
    }
    return 0;
}
int main(int argc,char **argv) {
    union REGS r;struct SREGS s;unsigned free_id,id,env,i;struct Resident far *found;
    unsigned seconds=120;FILE *background;char scene_path[128];
    setvbuf(stdout,0,_IONBF,0);
    id=find_resident(&free_id,&found);
    if(argc>1 && argv[1][0]=='/') {
        if(!id) {puts("DOS Scenes TSR is not loaded.");return 1;}
        r.x.ax=id<<8;
        if(!stricmp(argv[1],"/ON"))r.h.al=1;
        else if(!stricmp(argv[1],"/OFF"))r.h.al=2;
        else if(!stricmp(argv[1],"/SHOW"))r.h.al=3;
        else if(stricmp(argv[1],"/STATUS")) {puts("SCENETSR /ON | /OFF | /SHOW | /STATUS");return 1;}
        int86(0x2f,&r,&r);
        printf("DOS Scenes TSR: %s, %u seconds, %lu activations, %lu frames, error %u, resident %u paragraphs\n",found->enabled?"on":"off",found->timeout,found->activations,found->last_frames,found->last_error,found->paragraphs);
        return 0;
    }
    if(id) {puts("DOS Scenes TSR is already loaded. Use /SHOW, /OFF or /STATUS.");return 0;}
    if(argc<2 || !free_id) {puts("SCENETSR scene-directory [/IDLE=seconds]\nCtrl-Alt-S: show at DOS idle. Other keys wake; +/- M N control audio.\nNo setup utility. /OFF disables it; reboot removes the resident code.");return 1;}
    if(_osmajor<5 || !_fullpath(scene_directory,argv[1],sizeof(scene_directory))) {puts("DOS5+ and a valid scene directory are required.");return 1;}
    for(i=2;i<(unsigned)argc;i++) {
        if(strnicmp(argv[i],"/IDLE=",6) || atol(argv[i]+6)<0 || atol(argv[i]+6)>3600) {puts("Idle seconds must be0..3600;0 means hotkey only.");return 1;}
        seconds=(unsigned)atol(argv[i]+6);
    }
    sprintf(scene_path,"%s\\SCENE.EGA",scene_directory);background=fopen(scene_path,"rb");
    if(!background) { sprintf(scene_path,"%s\\ISLAND.EGA",scene_directory);background=fopen(scene_path,"rb"); }
    if(!background) {puts("Missing scene background.");return 1;}
    fseek(background,0,SEEK_END);
    if(ftell(background)!=32000L) {fclose(background);puts("Invalid scene background.");return 1;}
    fclose(background);
    resident.psp=_psp;resident.enabled=1;resident.timeout=seconds;resident.multiplex=free_id;
    memset(&r,0,sizeof(r));segread(&s);r.h.ah=0x34;int86x(0x21,&r,&r,&s);
    in_dos=(unsigned char far *)MK_FP(s.es,r.x.bx);
    critical_error=(unsigned char far *)(r.x.bx?MK_FP(s.es,r.x.bx-1):MK_FP(s.es-1,15));
    previous_clock=_dos_getvect(8);previous_keyboard=_dos_getvect(9);
    previous_idle=_dos_getvect(0x28);previous_mux=_dos_getvect(0x2f);
    resident.paragraphs=*(unsigned short far *)MK_FP(_psp-1,3);
    printf("DOS Scenes resident: %s, Ctrl-Alt-S, idle %u seconds; %u KB resident.\n",scene_directory,seconds,resident.paragraphs/64);
    fflush(stdout);
    env=*(unsigned short far *)MK_FP(_psp,0x2c);
    if(env) {_dos_freemem(env);*(unsigned short far *)MK_FP(_psp,0x2c)=0;}
    _disable();_dos_setvect(8,clock_handler);_dos_setvect(9,keyboard_handler);
    _dos_setvect(0x28,idle_handler);_dos_setvect(0x2f,(Handler)mux_handler);_enable();
    _dos_keep(0,resident.paragraphs);return 0;
}
