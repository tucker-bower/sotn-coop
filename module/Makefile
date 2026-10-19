# Builds the co-op module (see coop_api.h and boot.c). scripts/build_disc.sh puts it on the disc.
# Output: build/coop/boot.bin (appended to DRA.BIN), build/coop/COOP.BIN (a disc file),
# and build/coop/coop.map for harness symbol lookup.
VERSION   ?= us
ROOT      := ../../..
BUILD     := $(ROOT)/build/coop
CONFIG    := $(ROOT)/config
CROSS     := mipsel-linux-gnu-
CC_FLAGS  := -std=c11 -c -G0 -O2 -g -funsigned-char -fno-builtin -fno-tree-loop-distribute-patterns -Werror -Wall -Wno-unused-function
CC_FLAGS  += -march=mips1 -mabi=32 -EL -mfp32 -fno-pic -mno-shared -mno-abicalls -fno-stack-protector -nostdlib
CPP_FLAGS := -isystem $(ROOT)/include -isystem $(ROOT)/include/psxsdk -undef
CPP_FLAGS += -D_internal_version_$(VERSION) -Dmips -D__OPTIMIZE__ -D__mips__ -D__mips -Dpsx -D__psx__ -D__psx
CPP_FLAGS += -D_PSYQ -D__EXTENSIONS__ -D_MIPSEL -DNO_LOGS -D_LANGUAGE_C -DLANGUAGE_C
OBJS      := $(BUILD)/boot.o $(BUILD)/coop.o $(BUILD)/arrive.o $(BUILD)/progress.o $(BUILD)/flag_gated.o $(BUILD)/puppet.o
# boot.bin must fit in DRA.BIN's last CD sector (DRA.BIN is 0x119870 bytes; 564 sectors = 0x11A000)
BOOT_MAX  := 1936

all: $(BUILD)/boot.bin $(BUILD)/COOP.BIN

$(BUILD)/boot.bin: $(BUILD)/coop.elf
	$(CROSS)objcopy -O binary -j .boot $< $@
	@test $$(stat -c %s $@) -le $(BOOT_MAX) || { echo "boot.bin exceeds $(BOOT_MAX) bytes"; exit 1; }

$(BUILD)/COOP.BIN: $(BUILD)/coop.elf
	$(CROSS)objcopy -O binary -R .boot $< $@

$(BUILD)/coop.elf: $(OBJS) coop.ld $(BUILD)/symbols.ld.txt
	$(CROSS)ld -o $@ -Map $(BUILD)/coop.map -T coop.ld -T $(BUILD)/symbols.ld.txt $(OBJS)

# Shared globals from config/, every DRA symbol from the build's map (e.g. DebugUpdate), and the
# main.exe globals DRA itself links against (e.g. D_8003C730).
DRA_MAP := $(ROOT)/build/$(VERSION)/dra.map
$(BUILD)/symbols.ld.txt: $(CONFIG)/symbols.$(VERSION).txt $(DRA_MAP) Makefile
	mkdir -p $(BUILD)
	grep -o '^[^/]*' $(CONFIG)/symbols.$(VERSION).txt > $@
	awk '$$1 ~ /^0x80/ && NF == 2 && $$2 ~ /^[A-Za-z_][A-Za-z0-9_]*$$/ { print $$2 " = " $$1 ";" }' $(DRA_MAP) >> $@
	cat $(ROOT)/build/$(VERSION)/config/undefined_syms_auto.$(VERSION).dra.txt >> $@  # main.exe globals DRA uses

$(BUILD)/%.o: %.c coop_api.h link.h arrive.h progress.h flag_gated.h puppet.h
	mkdir -p $(BUILD)
	$(CROSS)cpp $(CPP_FLAGS) -o $(BUILD)/$*.i $<
	$(CROSS)gcc $(CC_FLAGS) -x cpp-output -o $@ $(BUILD)/$*.i

clean:
	rm -rf $(BUILD)
.PHONY: all clean
