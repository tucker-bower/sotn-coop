# Ultimate Maria (docs/design/character-mods.md): SOTN Ultimate's PSP Maria, upstream's src/maria
# built as Ultimate builds it (its tools/build_mar2.sh: no COOP_MARIA, MOD_SATURN for its crouch
# fix) with its glue, mar2.c, and the co-op hooks there. Her assets and voice are Co-op Maria's
# (characters/maria-dx), made from the USA DXC disc. Never shipped: the launcher rebuilds her on
# the player's PC from their own disc and patches of our changes (make_patches.py).
VERSION ?= us
ROOT    ?= $(shell if [ -f ../../.env/src/sotn-decomp/sotn.sh ]; then echo ../../.env/src/sotn-decomp; else echo ../../../..; fi)
BUILD   := $(ROOT)/build/coop/maria-ultimate
SRC     := $(ROOT)/src/maria
ASSETS  := $(ROOT)/build/coop/maria/.assets
CROSS   := mipsel-linux-gnu-
CFLAGS  := -mno-abicalls -G0 -fno-pic -g -O2 -I$(ROOT)/include -I$(ROOT)/include/psxsdk -I$(SRC) -msoft-float -march=3000
CFLAGS  += -funsigned-char -fpeephole -ffunction-cse -fpcc-struct-return -fcommon -fno-stack-protector
CFLAGS  += -fno-toplevel-reorder -fdata-sections -D_internal_version_us -DMARIA_SFX_MOD=1 -DMOD_SATURN -w
CFLAGS  += -include $(CURDIR)/coop_ult_maria.h -I$(CURDIR)
SRCS    := $(notdir $(wildcard $(SRC)/*.c))
OBJS    := $(BUILD)/mar2.o $(patsubst %.c,$(BUILD)/%.o,$(SRCS))
PBUILD  := $(BUILD)/partner
POBJS   := $(PBUILD)/mar2.o $(patsubst %.c,$(PBUILD)/%.o,$(SRCS)) $(PBUILD)/coop_partner.o

all: $(BUILD)/ULTMAR.BIN $(BUILD)/ULTMARP.BIN

# her art, extracted once for Co-op Maria
$(ASSETS):
	$(MAKE) -C ../maria-dx $(ASSETS)

$(BUILD)/mar2.o: mar2.c coop_ult_maria.h $(ASSETS)
	@mkdir -p $(BUILD)
	$(CROSS)gcc $(CFLAGS) -c $< -o $@
$(BUILD)/%.o: $(SRC)/%.c coop_ult_maria.h $(ASSETS)
	@mkdir -p $(BUILD)
	$(CROSS)gcc $(CFLAGS) -c $< -o $@
$(PBUILD)/mar2.o: mar2.c coop_ult_maria.h $(ASSETS)
	@mkdir -p $(PBUILD)
	$(CROSS)gcc $(CFLAGS) -DCOOP_PARTNER -c $< -o $@
$(PBUILD)/coop_partner.o: ../richter-ps1/coop_partner.c $(ASSETS)
	@mkdir -p $(PBUILD)
	$(CROSS)gcc $(CFLAGS) -DCOOP_PARTNER -c $< -o $@
$(PBUILD)/%.o: $(SRC)/%.c coop_ult_maria.h $(ASSETS)
	@mkdir -p $(PBUILD)
	$(CROSS)gcc $(CFLAGS) -DCOOP_PARTNER -c $< -o $@

$(BUILD)/symbols.txt: $(ROOT)/config/symbols.$(VERSION).txt
	@mkdir -p $(BUILD)
	sed 's;//.*;;' $< > $@
	echo 'g_SfxData = 0x800BF554;' >> $@

# the module finds her hooks at fixed addresses (ult_maria.ld): checked here
$(BUILD)/ultmar.elf: $(OBJS) $(BUILD)/symbols.txt ult_maria.ld
	$(CROSS)ld -nostdlib -Map=$(BUILD)/ultmar.map --build-id=none -T ult_maria.ld \
	    -T $(ROOT)/config/undefined_syms.$(VERSION).txt -T $(BUILD)/symbols.txt -o $@ $(OBJS)
	@$(CROSS)nm $@ | grep -q '^8013c1f0 D CoopMarBanks' || { echo "CoopMarBanks isn't at 0x8013C1F0"; exit 1; }
	@$(CROSS)nm $@ | grep -q '^8013c7f8 D CoopUltMarHooks' || { echo "CoopUltMarHooks isn't at 0x8013C7F8"; exit 1; }

$(BUILD)/ULTMAR.BIN: $(BUILD)/ultmar.elf
	$(CROSS)objcopy -O binary $< $@
	@echo "ULTMAR.BIN: $$(stat -c %s $@) bytes"

$(BUILD)/ultmarp.elf: $(POBJS) $(BUILD)/symbols.txt ult_maria_partner.ld
	$(CROSS)ld -nostdlib -Map=$(BUILD)/ultmarp.map --build-id=none -T ult_maria_partner.ld \
	    -T $(ROOT)/config/undefined_syms.$(VERSION).txt -T $(BUILD)/symbols.txt -o $@ $(POBJS)

$(BUILD)/ULTMARP.BIN: $(BUILD)/ultmarp.elf
	$(CROSS)objcopy -O binary $< $@
	@echo "ULTMARP.BIN: $$(stat -c %s $@) bytes"

.PHONY: all
