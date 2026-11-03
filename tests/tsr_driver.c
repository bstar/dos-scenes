/* Exercise resident entry from another PSP and stack, not a linked-in mock. */
#include <dos.h>
#include <i86.h>
#include <bios.h>
#include <conio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <malloc.h>
typedef void (__interrupt __far *Handler)(void);
struct Probe { unsigned enabled,pending,busy,timeout,multiplex,error,psp,paragraphs;unsigned long idle,activations,frames; };
static struct Probe far *resident;
static unsigned id;
static unsigned short cells[2000];
static Handler vectors[6];
static unsigned psp(void){union REGS r;r.h.ah=0x51;int86(0x21,&r,&r);return r.x.bx;}
static void far *dta(void){union REGS r;struct SREGS s;r.h.ah=0x2f;segread(&s);int86x(0x21,&r,&r,&s);return MK_FP(s.es,r.x.bx);}
static void command(unsigned sub){union REGS r;r.x.ax=(id<<8)|sub;int86(0x2f,&r,&r);}
static unsigned long font_hash(void){
 unsigned s2,s4,g4,g5,g6,seq=inp(0x3c4),gc=inp(0x3ce),i;unsigned long hash=5381;unsigned char far *v=MK_FP(0xa000,0);
 outp(0x3c4,2);s2=inp(0x3c5);outp(0x3c4,4);s4=inp(0x3c5);
 outp(0x3ce,4);g4=inp(0x3cf);outp(0x3ce,5);g5=inp(0x3cf);outp(0x3ce,6);g6=inp(0x3cf);
 outpw(0x3c4,0x0402);outpw(0x3c4,0x0604);outpw(0x3ce,0x0204);outpw(0x3ce,0x0005);outpw(0x3ce,0x0406);
 for(i=0;i<8192;i++)hash=(hash*33)^v[i];
 outpw(0x3c4,(s2<<8)|2);outpw(0x3c4,(s4<<8)|4);outpw(0x3ce,(g4<<8)|4);outpw(0x3ce,(g5<<8)|5);outpw(0x3ce,(g6<<8)|6);outp(0x3c4,seq);outp(0x3ce,gc);return hash;
}
static void text_mode(void){union REGS r;r.x.ax=3;int86(0x10,&r,&r);}
int main(int argc,char **argv){
 union REGS r;union REGPACK rp;struct SREGS s;unsigned n,i,owner;unsigned long start,hash,count;void far *saved_dta,*reserve[16];
 unsigned char custom_dta[128],glyph[16]={0,24,60,126,255,126,60,24,24,60,126,255,126,60,24,0};FILE *f;
 freopen("TSRERR.TXT","w",stderr);setvbuf(stderr,0,_IONBF,0);
 for(id=0xc0;id<=255;id++) {
  memset(&r,0,sizeof(r));r.x.ax=id<<8;segread(&s);int86x(0x2f,&r,&r,&s);
  if(r.h.al==255 && r.x.bx==0x5343 && r.x.cx==0x4e45){resident=MK_FP(s.es,r.x.di);break;}
 }
 assert(resident && resident->enabled && !resident->busy);
 assert(resident->paragraphs<8192); /* Less than128KiB resident, not all free DOS RAM. */
 text_mode();
 for(i=0;i<2000;i++)cells[i]=(unsigned short)(((i%15+1)<<8)|('A'+i%26));
 _fmemcpy(MK_FP(0xb800,0),cells,4000);
 memset(&rp,0,sizeof(rp));rp.w.es=FP_SEG(glyph);rp.w.bp=FP_OFF(glyph);rp.w.ax=0x1110;rp.w.cx=1;rp.w.dx=65;rp.w.bx=0x1000;intr(0x10,&rp);
 r.h.ah=1;r.x.cx=0x040a;int86(0x10,&r,&r);r.h.ah=2;r.h.bh=0;r.x.dx=0x0c22;int86(0x10,&r,&r);
 outp(0x3c8,2);outp(0x3c9,12);outp(0x3c9,23);outp(0x3c9,34);
 hash=font_hash();owner=psp();saved_dta=dta();
 segread(&s);s.ds=FP_SEG(custom_dta);r.x.dx=FP_OFF(custom_dta);r.h.ah=0x1a;int86x(0x21,&r,&r,&s);
 vectors[0]=_dos_getvect(8);vectors[1]=_dos_getvect(9);vectors[2]=_dos_getvect(0x28);vectors[3]=_dos_getvect(0x2f);vectors[4]=_dos_getvect(0x23);vectors[5]=_dos_getvect(0x24);
 if(argc>1) {
  start=*(volatile unsigned long far *)MK_FP(0x40,0x6c);
  while(!resident->pending && *(volatile unsigned long far *)MK_FP(0x40,0x6c)-start<60){}
  assert(resident->pending==1);
 } else command(3);
 start=*(volatile unsigned long far *)MK_FP(0x40,0x6c);int86(0x28,&r,&r);
 assert(resident->activations==1 && resident->frames>5 && !resident->busy && !resident->error);
 assert(*(volatile unsigned long far *)MK_FP(0x40,0x6c)-start>10);
 assert(psp()==owner && dta()==(void far *)custom_dta);
 assert(*(unsigned char far *)MK_FP(0x40,0x49)==3);
 assert(!_fmemcmp(MK_FP(0xb800,0),cells,4000));assert(font_hash()==hash);
 outp(0x3c7,2);assert(inp(0x3c9)==12 && inp(0x3c9)==23 && inp(0x3c9)==34);
 r.h.ah=3;r.h.bh=0;int86(0x10,&r,&r);assert(r.x.cx==0x040a && r.x.dx==0x0c22);
 assert(vectors[0]==_dos_getvect(8) && vectors[1]==_dos_getvect(9) && vectors[2]==_dos_getvect(0x28) && vectors[3]==_dos_getvect(0x2f) && vectors[4]==_dos_getvect(0x23) && vectors[5]==_dos_getvect(0x24));
 command(2);count=resident->activations;command(3);int86(0x28,&r,&r);assert(resident->activations==count);
 command(1);r.x.ax=0x13;int86(0x10,&r,&r);command(3);int86(0x28,&r,&r);assert(resident->error==2 && *(unsigned char far *)MK_FP(0x40,0x49)==0x13);
 text_mode();n=0;while(n<16 && (reserve[n]=_fmalloc(60000U))!=0)n++;
 command(3);int86(0x28,&r,&r);assert(resident->error==1 && !resident->busy && psp()==owner && dta()==(void far *)custom_dta);
 for(i=0;i<n;i++)_ffree(reserve[i]);_fheapshrink();
 resident->timeout=1;resident->idle=0;start=*(volatile unsigned long far *)MK_FP(0x40,0x6c);
 while(*(volatile unsigned long far *)MK_FP(0x40,0x6c)-start<21){}
 assert(resident->pending==2);r.h.ah=5;r.x.cx=0x011b;int86(0x16,&r,&r);int86(0x28,&r,&r);assert(resident->activations==count+1 && !resident->error);
 resident->timeout=0;segread(&s);s.ds=FP_SEG(saved_dta);r.x.dx=FP_OFF(saved_dta);r.h.ah=0x1a;int86x(0x21,&r,&r,&s);
 command(2);f=fopen("TSRPASS.TXT","w");assert(f);fprintf(f,"PASS resident=%uKB: manual/idle entry, private stack, PSP/DTA, IRQ, text/font/DAC/cursor, off/on, graphics/low-memory deferral\n",resident->paragraphs/64);fclose(f);
 return 0;
}
