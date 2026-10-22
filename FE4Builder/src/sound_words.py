"""Native FE4 sound-word meanings verified from handlers, call sites and private SPC traces."""
WORD_INFO={
    0x000a:dict(label='Menu confirmation cue',description='Used when accepting a map-menu action with A. Plays a sound sequence; it does not change the music volume. Its sound depends on the loaded sound bank.',evidence='Use verified in native menu code; exact sound-bank identity is not independently named.'),
    0x0014:dict(label='Dialogue text blip (variant 3)',description='The dialogue text-sound routine uses this cue for text-sound setting 3. This is a text/voice blip, not a music fade. Its sound depends on the loaded bank.',evidence='Verified in rsDialoguePlayTextSound at CPU $9189B4.'),
    0x0021:dict(label='Menu cancel / back cue',description='Used when backing out of a map-menu action with B. Plays a sound sequence without changing the music volume; its sound depends on the loaded bank.',evidence='Use verified in native menu code; exact sound-bank identity is not independently named.'),
    0x00d0:dict(label='Music synchronization signal',description='Sets an audio-driver synchronization flag, which a waiting music sequence can check. It does not select a track or perform a fade. The precise audible cue affected in each scene is not fully verified.',evidence='Flag write and sequence wait check verified in SPC code; scene-specific musical purpose remains partly understood.',confidence='Partly understood'),
    0x00e8:dict(label='Restore music volume (~0.5 s)',description='Fades music volume up to its full internal level of 255 over 31 driver ticks (about 0.5 seconds in the preview). It restores music ducked by $00F7 / $7FF7. It does not choose a track or restart music already stopped by a completed fade-out.',evidence='SPC handler and volume traces verified; native village scripts pair $7FF7 with $00E8.',ticks=31,target=255,preview_note='With background music selected, the preview first reduces its volume so this restoration can be heard.'),
    0x00f7:dict(label='Duck music to 60/255 (~24%)',description='Fades music volume to internal level 60 over 24 driver ticks (about 0.4 seconds), leaving the track running. With a zero high byte, the driver uses 60 as its default target. $00E8 restores full volume.',evidence='SPC parameter handler and final-volume trace verified.',ticks=24,target=60),
    0x7ff7:dict(label='Duck music to 127/255 (~50%)',description='Fades music volume to internal level 127 over 24 driver ticks (about 0.4 seconds), leaving the track running. The high byte $7F supplies the target level: this is not interchangeable with $00F7. Commonly used to lower background music during village dialogue/rewards; $00E8 restores it.',evidence='SPC high-byte parameter handling, native village call sites and final-volume trace verified.',ticks=24,target=127),
}
for step in range(8):
    ticks=32*(step+1)-1;seconds=ticks/62.5
    WORD_INFO[0xe0+step]=dict(label=f'Fade out / stop music (~{seconds:.1f} s)',
        description=f'Fades music volume to zero over {ticks} driver ticks (about {seconds:.1f} seconds in the preview), then stops the current music sequence. $00E0 is fastest; $00E7 is slowest. To hear music again after completion, use Play Song; $00E8 alone does not restart the stopped track.',
        evidence='SPC fade handler, countdown and stopped-sequence traces verified. Times are approximate and specific to the native driver.',ticks=ticks,target=0)
for info in WORD_INFO.values():info.setdefault('confidence','Verified for native FE4')

def word_info(value):return WORD_INFO.get(value)

def describe_word(value):
    info=word_info(value)
    if info is None:return 'Unknown sound-word behavior. No detailed interpretation is verified for this value.'
    result=info['label']+f' · ${value:04X}\n'+info['description']+'\nEvidence: '+info['evidence']
    if info.get('preview_note'):result+='\nPreview: '+info['preview_note']
    if info['confidence']=='Partly understood':result+='\nStatus: partly understood; do not assume this starts an audible effect.'
    return result
