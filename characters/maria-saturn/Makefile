# Saturn Maria (docs/design/character-mods.md): SOTN Ultimate's src/ric built with MOD_MARIA_SAT,
# as its tools/build_mar.sh does, but with our toolchain (Co-op Richter's recipe: modern gcc, data
# in Richter's slot, code in the 8MB) and against our headers. Her sources: upstream's src/ric at
# the pinned commit, plus Ultimate's changes (ultimate-ric.patch, from SOTN Ultimate df11991) and
# its maria_saturn headers. Her art is generated from the Saturn disc into $(GEN): on the dev
# machine by Ultimate's own converters (gen_mar_assets.py, gen_mar_sounds.py in an Ultimate
# checkout, $(ULT)).
VERSION ?= us
ROOT    ?= $(shell if [ -f ../../.env/src/sotn-decomp/sotn.sh ]; then echo ../../.env/src/sotn-decomp; else echo ../../../..; fi)
ULT     ?= /home/tucker/research-src/sotn-ultimate
GEN     ?= $(ULT)/build/us/mod/mar
BUILD   := $(ROOT)/build/coop/maria-saturn
TREE    := $(BUILD)/tree
SRC     := $(TREE)/src/ric
CROSS   := mipsel-linux-gnu-
CFLAGS  := -mno-abicalls -G0 -fno-pic -g -O2 -I$(GEN) -I$(SRC) -I$(ROOT)/src/ric -I$(ROOT)/include -I$(ROOT)/include/psxsdk
CFLAGS  += -msoft-float -march=r3000 -funsigned-char -fno-builtin -fcommon -fno-toplevel-reorder -fdata-sections
CFLAGS  += -fno-stack-protector -D_internal_version_$(VERSION) -DMOD_MARIA_SAT -Dabs=__builtin_abs -Dlabs=__builtin_labs
CFLAGS  += -Wno-implicit-function-declaration -Wno-int-conversion -Wno-incompatible-pointer-types -w
SRCS    := pl_header.c $(filter-out pl_header.c ovl_load.c,$(notdir $(wildcard $(ROOT)/src/ric/*.c)))
OBJS    := $(patsubst %.c,$(BUILD)/%.o,$(SRCS))

all: $(BUILD)/SATMAR.BIN

# upstream's src/ric, then Ultimate's changes; its includes of "../../mods/sotn-ultimate/src/
# maria_saturn/..." find ours
$(TREE)/.patched: ultimate-ric.patch $(wildcard maria_saturn/*.h)
	@mkdir -p $(TREE)/mods/sotn-ultimate/src
	git -C $(ROOT) archive HEAD src/ric | tar -x -C $(TREE)
	patch -s -p1 -d $(TREE) < ultimate-ric.patch  # not git apply: the tree is inside the decomp's repo
	ln -sfn $(CURDIR)/maria_saturn $(TREE)/mods/sotn-ultimate/src/maria_saturn
	touch $@

$(BUILD)/%.o: $(TREE)/.patched
	@mkdir -p $(BUILD)
	$(CROSS)gcc $(CFLAGS) -c $(SRC)/$*.c -o $@

$(BUILD)/symbols.txt: $(ROOT)/config/symbols.$(VERSION).txt
	@mkdir -p $(BUILD)
	sed 's;//.*;;' $< > $@
	echo 'g_ClutIds = 0x8003C104;' >> $@
	echo 'g_CdVolume = 0x8013B668;' >> $@
	echo 'g_XaMusicVolume = 0x80139820;' >> $@
	echo 'D_8006BB00 = 0x8006BB00;' >> $@

$(BUILD)/satmar.elf: $(OBJS) $(BUILD)/symbols.txt sat_maria.ld
	$(CROSS)ld -nostdlib -Map=$(BUILD)/satmar.map --build-id=none -T sat_maria.ld \
	    -T $(ROOT)/config/undefined_syms.$(VERSION).txt -T $(BUILD)/symbols.txt -o $@ $(OBJS)

$(BUILD)/SATMAR.BIN: $(BUILD)/satmar.elf
	$(CROSS)objcopy -O binary $< $@
	@echo "SATMAR.BIN: $$(stat -c %s $@) bytes; data $$($(CROSS)size -A $< | awk '$$1==".data"{print $$2}') of $$((0x80170000 - 0x8013C000))"

.PHONY: all
