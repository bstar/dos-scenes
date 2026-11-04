/* Capture the real renderer's planar pages and scene clock for documentation. */
#include "../src/dos_scenes.h"
#include <dos.h>
#include <conio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <malloc.h>
#include <assert.h>
static unsigned char buffer[8000];
int main(void) {
 FILE *f;unsigned p,base;unsigned long previous=0,first=0,limit=8400UL;
 assert(dsBegin("C:\\ISLAND"));f=fopen("TAKE.RAW","wb");assert(f);
 while(!previous || dsSceneTicks-first<limit) {
  dsStep();if(dsFrames==previous)continue;
  if(!previous)first=dsSceneTicks;previous=dsFrames;
  assert(fwrite(&dsSceneTicks,4,1,f)==1);assert(fwrite(&dsFrames,4,1,f)==1);
  base=(dsFrames&1)?8192:0;
  for(p=0;p<4;p++) {
   outp(0x3ce,4);outp(0x3cf,p);_fmemcpy(buffer,(void far *)MK_FP(0xa000,base),8000);
   assert(fwrite(buffer,1,8000,f)==8000);
  }
 }
 assert(!dsFault);fclose(f);dsEnd();printf("Captured %lu frames from tick %lu to %lu\n",previous,first,dsSceneTicks);return 0;
}
