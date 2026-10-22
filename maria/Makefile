# Our Maria (design/M8, M8b): src/maria (the PSP Dracula X Chronicles player) built for the PS1
# with the co-op changes (COOP_MARIA), the way upstream's mods/mariapsp-forpsx does, from the
# USA DXC disc (disks/pspus). The output is never shipped: the launcher rebuilds it on the
# player's PC from their own DXC disc and a patch of our changes only (design/M8 §4).
VERSION ?= us
ROOT    ?= $(shell if [ -f ../.env/src/sotn-decomp/sotn.sh ]; then echo ../.env/src/sotn-decomp; else echo ../../..; fi)
BUILD   := $(ROOT)/build/coop/maria
SRC     := $(ROOT)/src/maria
GLUE    := $(ROOT)/mods/mariapsp-forpsx/maria.c
PSPBIN  := $(ROOT)/disks/pspus/PSP_GAME/USRDIR/res/ps/PSPBIN/maria.bin
SPK     := $(ROOT)/disks/pspus/PSP_GAME/USRDIR/res/ps/snd_e/SE/sd_mar2.spk
CROSS   := mipsel-linux-gnu-
CFLAGS  := -mno-abicalls -G0 -fno-pic -g -O2 -I$(ROOT)/include -I$(ROOT)/include/psxsdk -I$(SRC) -msoft-float -march=3000
CFLAGS  += -funsigned-char -fpeephole -ffunction-cse -fpcc-struct-return -fcommon -fno-stack-protector
CFLAGS  += -fno-toplevel-reorder -fdata-sections -DMARIA_SFX_MOD=1 -DCOOP_MARIA -include $(CURDIR)/coop_maria.h
CFLAGS  += -I$(CURDIR)/../richter
SRCS    := $(notdir $(wildcard $(SRC)/*.c))
OBJS    := $(BUILD)/maria.o $(patsubst %.c,$(BUILD)/%.o,$(SRCS)) $(BUILD)/coop_maria.o
# The European HUD languages aren't on the USA disc; only the PSP build uses them.
EU_ONLY := font_eu hud_sp hud_it hud_ge hud_fr

all: $(BUILD)/MARIA.BIN $(BUILD)/sfx/.built

$(BUILD)/.assets: $(PSPBIN) assets.pspus.maria.yaml splat.pspus.maria.yaml
	@mkdir -p $(BUILD)
	cp assets.pspus.maria.yaml splat.pspus.maria.yaml $(ROOT)/config/
	cd $(ROOT) && ./sotn.sh extract-assets config/assets.pspus.maria.yaml && ./sotn.sh build-assets config/assets.pspus.maria.yaml
	for f in $(EU_ONLY); do echo "0, // not on the USA disc; used only by the PSP build" > $(SRC)/gen/$$f.h; done
	touch $@

$(BUILD)/maria.o: $(GLUE) coop_maria.h $(BUILD)/.assets
	$(CROSS)gcc $(CFLAGS) -c $< -o $@
$(BUILD)/coop_maria.o: coop_maria.c coop_maria.h $(BUILD)/.assets
	$(CROSS)gcc $(CFLAGS) -c $< -o $@
$(BUILD)/%.o: $(SRC)/%.c coop_maria.h $(BUILD)/.assets
	$(CROSS)gcc $(CFLAGS) -c $< -o $@

$(BUILD)/symbols.txt: $(ROOT)/config/symbols.$(VERSION).txt
	@mkdir -p $(BUILD)
	sed 's;//.*;;' $< > $@
	echo 'g_SfxData = 0x800BF554;' >> $@

$(BUILD)/maria.elf: $(OBJS) $(BUILD)/symbols.txt maria.ld ../richter/coop_player.ld
	$(CROSS)ld -nostdlib -Map=$(BUILD)/maria.map --build-id=none -T $(ROOT)/mods/mariapsp-forpsx/symexport.txt \
	    -T maria.ld -T $(ROOT)/config/undefined_syms.$(VERSION).txt -T $(BUILD)/symbols.txt \
	    -T ../richter/coop_player.ld -o $@ $(OBJS)

$(BUILD)/MARIA.BIN: $(BUILD)/maria.elf
	$(CROSS)objcopy -O binary $< $@
	@echo "MARIA.BIN: $$(stat -c %s $@) bytes (Richter's slot holds $$((0x80180000 - 0x8013C000)))"

$(BUILD)/sfx/.built: $(SPK)
	cargo run --quiet --manifest-path $(ROOT)/tools/maria-sfx/Cargo.toml -- build $< $(BUILD)/sfx
	touch $@

clean:
	rm -rf $(BUILD)
.PHONY: all clean
