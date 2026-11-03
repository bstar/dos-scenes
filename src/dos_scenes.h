/* Cooperative DOS scene runtime. Original code licensed under MIT. */
#ifndef DOS_SCENES_H
#define DOS_SCENES_H
#ifdef __cplusplus
extern "C" {
#endif
int dsBegin(const char *directory);
void dsStep(void);
void dsEnd(void);
int dsKey(unsigned key);
unsigned dsGetVolume(void);
extern unsigned long dsFrames,dsSceneTicks;
extern unsigned dsError,dsAdlib,dsFault;
#ifdef __cplusplus
}
#endif
#endif
