/* Real DOS cross-process persistence, debounce, muted/zero and I/O recovery. */
#include <dos.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <direct.h>
#include <assert.h>
#include "../src/dos_scenes.h"
static void text(const char *name,const char *value) {
 FILE *f=fopen(name,"wb");assert(f);fputs(value,f);assert(!fclose(f));
}
static unsigned saved(void) {
 unsigned v;FILE *f=fopen("C:\\DEMO\\VOLUME.CFG","rb");assert(f);
 assert(fscanf(f,"%u",&v)==1);fclose(f);return v;
}
static void begin(unsigned volume) {
 assert(dsBegin("C:\\DEMO"));assert(dsGetVolume()==volume);
}
int main(int argc,char **argv) {
 unsigned i;
 freopen("C:\\VOLTEST.LOG","a",stderr);assert(argc==2);
 if(!strcmp(argv[1],"set")) {
  begin(28);for(i=0;i<4;i++)assert(dsKey('-'));assert(dsGetVolume()==24);
  while(dsFrames<28)dsStep();assert(saved()==24);dsEnd();puts("SET24 debounce saved while active");
 } else if(!strcmp(argv[1],"muted")) {
  begin(24);assert(dsKey('m'));assert(dsKey('-'));assert(dsGetVolume()==23);
  dsEnd();assert(saved()==23);puts("RELOAD24 and muted change saved23 on immediate wake");
 } else if(!strcmp(argv[1],"zero")) {
  begin(23);for(i=0;i<32;i++)dsKey('-');dsEnd();assert(saved()==0);
  begin(0);dsKey('+');dsEnd();assert(saved()==1);puts("ZERO persisted and plus restores1");
 } else if(!strcmp(argv[1],"shared")) {
  begin(2);dsEnd();puts("SHARED standalone change reloaded2");
 } else if(!strcmp(argv[1],"recovery")) {
  text("C:\\DEMO\\VOLUME.CFG","999junk\r\n");begin(1);dsEnd();
  text("C:\\DEMO\\VOLUME.CFG","invalid\r\n");text("C:\\DEMO\\VOLUME.BAK","invalid\r\n");
  begin(28);dsEnd();
  assert(!mkdir("C:\\DEMO\\VOLSET.TMP"));begin(28);dsKey('-');dsEnd();
  assert(!rmdir("C:\\DEMO\\VOLSET.TMP"));begin(27);dsEnd();assert(saved()==27);
  puts("RECOVERY backup, invalid default and failed-save retry");
 } else assert(0);
 return 0;
}
