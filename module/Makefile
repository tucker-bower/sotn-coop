# Builds the co-op module as a TT_000.BIN replacement (see inject.c). Adapted from tools/sotn-debugmodule.
# Output: build/coop/coop.bin (+ coop.map for harness symbol lookup)
VERSION   ?= us
ROOT      := ../../..
BUILD     := $(ROOT)/build/coop
CONFIG    := $(ROOT)/config
CROSS     := mipsel-linux-gnu-
CC_FLAGS  := -std=c11 -c -G0 -O2 -g -funsigned-char -Werror -Wall -Wno-unused-function
CC_FLAGS  += -march=mips1 -mabi=32 -EL -mfp32 -fno-pic -mno-shared -mno-abicalls -fno-stack-protector -nostdlib
CPP_FLAGS := -isystem $(ROOT)/include -isystem $(ROOT)/include/psxsdk -undef
CPP_FLAGS += -D_internal_version_$(VERSION) -Dmips -D__OPTIMIZE__ -D__mips__ -D__mips -Dpsx -D__psx__ -D__psx
CPP_FLAGS += -D_PSYQ -D__EXTENSIONS__ -D_MIPSEL -DNO_LOGS -D_LANGUAGE_C -DLANGUAGE_C
OBJS      := $(BUILD)/inject.o $(BUILD)/coop.o   # inject.o first: its header must start the binary
SLOT_SIZE := 40960

all: $(BUILD)/coop.bin

$(BUILD)/coop.bin: $(BUILD)/coop.elf
	$(CROSS)objcopy -O binary $< $@
	@test $$(stat -c %s $@) -le $(SLOT_SIZE) || { echo "coop.bin exceeds the $(SLOT_SIZE)-byte TT_000 slot"; exit 1; }
	truncate -s $(SLOT_SIZE) $@

$(BUILD)/coop.elf: $(OBJS) coop.ld $(BUILD)/symbols.ld.txt
	$(CROSS)ld -o $@ -Map $(BUILD)/coop.map -T coop.ld -T $(BUILD)/symbols.ld.txt $(OBJS)

# Shared globals from config/, plus every DRA symbol from the matching build's map (e.g. DebugUpdate).
DRA_MAP := $(ROOT)/build/$(VERSION)/dra.map
$(BUILD)/symbols.ld.txt: $(CONFIG)/symbols.$(VERSION).txt $(DRA_MAP) Makefile
	mkdir -p $(BUILD)
	grep -o '^[^/]*' $(CONFIG)/symbols.$(VERSION).txt > $@
	awk '$$1 ~ /^0x80/ && NF == 2 && $$2 ~ /^[A-Za-z_][A-Za-z0-9_]*$$/ { print $$2 " = " $$1 ";" }' $(DRA_MAP) >> $@

$(BUILD)/%.o: %.c
	mkdir -p $(BUILD)
	$(CROSS)cpp $(CPP_FLAGS) -o $(BUILD)/$*.i $<
	$(CROSS)gcc $(CC_FLAGS) -x cpp-output -o $@ $(BUILD)/$*.i

clean:
	rm -rf $(BUILD)
.PHONY: all clean
