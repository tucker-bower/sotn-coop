/* Where DRA's COOP hooks (coop_api.h) jump. gen.py adds this to DRA's link when COOP=1.
   CoopBoot sits at the start of the module payload, right behind DRA's image
   (dra_data_VRAM_END, which the size-neutral hooks keep at 0x801B9870); the rest is the
   jump table at the start of the module in 8MB RAM (coop.ld). */
CoopBoot = 0x801B9870;
CoopUpdate = 0x80280000;
CoopRenderEntities = 0x80280008;
CoopDrawMapCursor = 0x80280010;
