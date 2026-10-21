# Our Richter (design/M8, M8b): src/ric built with the co-op changes (COOP_RIC), for the co-op
# disc's COOPRIC.BIN. The retail RIC.BIN stays on the disc for the prologue.
# Same recipe as upstream's mods/mariapsp-forpsx: a modern gcc, linked at Richter's address.
VERSION ?= us
ROOT    ?= $(shell if [ -f ../.env/src/sotn-decomp/sotn.sh ]; then echo ../.env/src/sotn-decomp; else echo ../../..; fi)
BUILD   := $(ROOT)/build/coop/ric
SRC     := $(ROOT)/src/ric
CROSS   := mipsel-linux-gnu-
CFLAGS  := -mno-abicalls -G0 -fno-pic -g -O2 -I$(ROOT)/include -I$(ROOT)/include/psxsdk -I$(SRC) -msoft-float -march=r3000
CFLAGS  += -funsigned-char -fno-builtin -fcommon -fno-toplevel-reorder -fdata-sections -fno-stack-protector -DVERSION_US -D_internal_version_$(VERSION) -DCOOP_RIC -Dabs=__builtin_abs -Dlabs=__builtin_labs
# ovl_load.c is the PSP build's loader.
CFLAGS  += -Wno-implicit-function-declaration -Wno-int-conversion -Wno-incompatible-pointer-types
# pl_header first: its .data (the g_PlOvl table DRA jumps through) must sit at 0x8013C000.
SRCS    := pl_header.c $(filter-out pl_header.c ovl_load.c,$(notdir $(wildcard $(SRC)/*.c)))
OBJS    := $(patsubst %.c,$(BUILD)/%.o,$(SRCS))

all: $(BUILD)/COOPRIC.BIN

$(BUILD)/%.o: $(SRC)/%.c
	@mkdir -p $(BUILD)
	$(CROSS)gcc $(CFLAGS) -c $< -o $@

$(BUILD)/symbols.txt: $(ROOT)/config/symbols.$(VERSION).txt
	@mkdir -p $(BUILD)
	sed 's;//.*;;' $< > $@

$(BUILD)/ric.elf: $(OBJS) $(BUILD)/symbols.txt ric.ld
	$(CROSS)ld -nostdlib -Map=$(BUILD)/ric.map --build-id=none -T ric.ld \
	    -T $(ROOT)/config/undefined_syms.$(VERSION).txt -T $(BUILD)/symbols.txt -o $@ $(OBJS)

$(BUILD)/COOPRIC.BIN: $(BUILD)/ric.elf
	$(CROSS)objcopy -O binary $< $@
	@echo "COOPRIC.BIN: $$(stat -c %s $@) bytes (Richter's slot holds $$((0x80180000 - 0x8013C000)))"

clean:
	rm -rf $(BUILD)
.PHONY: all clean
