// Owned instructions and sample values: checks lowering's register routing and Ampere->Maxwell expansions.
#include <array>
#include <bit>
#include <cmath>
#include <cstdio>
#include <vector>
#include "shader_recompiler/frontend/ampere/program_capture.h"

using namespace Shader::Ampere;
static unsigned checks, failures;
#define CHECK(x) do { ++checks; if (!(x)) { ++failures; std::fprintf(stderr, "line %d: %s\n", __LINE__, #x); } } while (0)

static void bits(Instruction& op, unsigned at, unsigned count, u32 value) {
    for (unsigned b = 0; b < count; ++b) {
        const unsigned word = (at + b) / 32, bit = (at + b) % 32;
        op.words[word] = (op.words[word] & ~(1u << bit)) | (((value >> b) & 1u) << bit);
    }
}

static Instruction make_exit() {
    Instruction exit{};
    bits(exit, 0, 12, 0x94d);
    bits(exit, 12, 4, 7);
    bits(exit, 87, 4, 7);
    return exit;
}

static LoweredProgram lower_txd(unsigned dest, unsigned mask, unsigned high, unsigned dimension, unsigned predicate) {
    Instruction txd{};
    bits(txd, 0, 12, 0xb6c);
    bits(txd, 12, 4, predicate);
    bits(txd, 16, 8, dest);         // first destination (pair when >=2 channels)
    bits(txd, 24, 8, 32);           // coordinates
    bits(txd, 32, 8, 40);           // derivatives
    bits(txd, 40, 14, 16);          // texture descriptor offset
    bits(txd, 54, 5, 3);            // texture constant buffer
    bits(txd, 61, 3, dimension);
    txd.words[2] = 0x001e0000 | mask << 8 | high;
    const std::array code{txd, make_exit()};
    return LowerToMaxwell(code, false);
}

static void check_txd_routing(unsigned dest, unsigned mask, unsigned high, unsigned dimension, unsigned predicate, bool p0) {
    const auto result = lower_txd(dest, mask, high, dimension, predicate);
    CHECK(bool(result));
    if (!result) {
        std::fprintf(stderr, "mask %u high %u dim %u pred %u: %.*s\n", mask, high, dimension, predicate,
                     int(result.error.size()), result.error.data());
        return;
    }
    CHECK(result.required_texture_buffer == 3);
    std::array<unsigned, 256> regs{}, expected{};
    for (unsigned r = 0; r < regs.size(); ++r) regs[r] = expected[r] = 1000 + r;
    const bool enabled = predicate == 7 || (predicate == 0 ? p0 : !p0);
    if (enabled) {
        unsigned out_idx = 0;
        for (unsigned c = 0; c < 4; ++c) {
            if (!((mask >> c) & 1u)) continue;
            if (out_idx >= 2 && high == 255) break;
            const unsigned to = out_idx < 2 ? dest + out_idx : high + (out_idx - 2);
            expected[to] = 11 * (c + 1);
            ++out_idx;
        }
    }
    unsigned textures = 0;
    for (const auto op : result.instructions) {
        if ((op >> 56) == 0xde) {
            ++textures;
            CHECK(((op >> 31) & 15) == mask);
            CHECK(((op >> 28) & 7) == (dimension == 5 ? 3u : 2u));
            CHECK(((op >> 8) & 255) == 32);
            CHECK(((op >> 20) & 255) == 40);
            CHECK(((op >> 36) & 0x1fff) == 16);
            CHECK(((op >> 16) & 15) == predicate);
            if (enabled) {
                unsigned dst = op & 255;
                unsigned out_idx = 0;
                for (unsigned c = 0; c < 4; ++c) {
                    if (!((mask >> c) & 1u)) continue;
                    regs[dst + out_idx++] = 11 * (c + 1);
                }
            }
        } else if ((op >> 48) == 0x5c98) {
            CHECK(((op >> 16) & 15) == predicate);
            if (enabled) regs[op & 255] = regs[(op >> 20) & 255];
        }
    }
    CHECK(textures == 1);
    for (unsigned r = 0; r < 248u; ++r) {
        CHECK(regs[r] == expected[r]);
    }
}

static void check_constant_load_offsets() {
    auto is_ldc = [](u64 w) { return (w >> 56) == 0xef; };
    auto is_cbuf_mov = [](u64 w) { return (w & 0xfff8000000000000ULL) == 0x4c98000000000000ULL; };
    auto wbits = [](u64 w, unsigned off, unsigned cnt) { return unsigned((w >> off) & ((u64{1} << cnt) - 1)); };

    // 1. IMAD.WIDE 0x625 with cbuf addend at 0x7ff8 vs 0x8000 / 0xfff8 / 0xfffc
    auto lower_625 = [](u32 offset) {
        Instruction op{{0x625U | (7U << 12) | (4U << 16) | (2U << 24), (2U << 22) | (offset << 6), 0x078e0000U | 4U, 0}};
        return LowerToMaxwell(std::array{op, make_exit()}, false);
    };
    {
        const auto low = lower_625(0x7ff8);
        CHECK(bool(low));
        unsigned ldc_n = 0, mov_n = 0;
        for (u64 w : low.instructions) { ldc_n += is_ldc(w); mov_n += is_cbuf_mov(w); }
        CHECK(ldc_n == 1 && mov_n == 0);
        for (u32 off : {0x8000U, 0xfff8U}) {
            const auto hi = lower_625(off);
            CHECK(bool(hi));
            std::vector<u64> movs;
            ldc_n = 0;
            for (u64 w : hi.instructions) { ldc_n += is_ldc(w); if (is_cbuf_mov(w)) movs.push_back(w); }
            CHECK(ldc_n == 0 && movs.size() == 2);
            if (movs.size() == 2) {
                for (unsigned h = 0; h < 2; ++h) {
                    CHECK(wbits(movs[h], 0, 8) == 252 + h);
                    CHECK(wbits(movs[h], 20, 14) == off / 4 + h);
                    CHECK(wbits(movs[h], 34, 5) == 2);
                    CHECK(wbits(movs[h], 39, 4) == 0xf);
                }
            }
        }
        CHECK(!lower_625(0xfffc));
    }

    // 2. ULDC.64 0xab9 UR4, c[2][offset] -> R220/R221
    auto lower_ab9 = [](u32 offset) {
        Instruction op{{0x00047ab9U, (2U << 22) | (offset << 6), 0xa00U, 0}};
        return LowerToMaxwell(std::array{op, make_exit()}, false);
    };
    {
        const auto low = lower_ab9(0x168);
        CHECK(bool(low));
        for (u32 off : {0x8000U, 0xfff8U}) {
            const auto hi = lower_ab9(off);
            CHECK(bool(hi));
            std::vector<u64> movs;
            for (u64 w : hi.instructions) if (is_cbuf_mov(w)) movs.push_back(w);
            CHECK(movs.size() == 2);
            if (movs.size() == 2) {
                CHECK(wbits(movs[0], 0, 8) == 220 && wbits(movs[1], 0, 8) == 221);
                CHECK(wbits(movs[0], 20, 14) == off / 4 && wbits(movs[1], 20, 14) == off / 4 + 1);
            }
        }
        CHECK(!lower_ab9(0xfffc));
    }
}

static void check_tanh_and_capture() {
    // MUFU.TANH R4, R2 (opcode 0x308, form 1 -> source in bits 32..39 = R2, operation = 9 in bits 74..79)
    Instruction tanh_op{};
    bits(tanh_op, 0, 12, 0x308);
    bits(tanh_op, 12, 4, 7);
    bits(tanh_op, 16, 8, 4);
    bits(tanh_op, 32, 8, 2);
    bits(tanh_op, 74, 6, 9);
    const auto lowered = LowerToMaxwell(std::array{tanh_op, make_exit()}, false);
    CHECK(bool(lowered));
    // Verify no MUFU instruction has op > 8 (so unmodified Ryujinx InstEmitMultifunction decodes every instruction).
    for (u64 w : lowered.instructions) {
        if ((w & 0xfff0000000000000ULL) == 0x5080000000000000ULL) {
            const unsigned mufu_op = unsigned((w >> 20) & 0xf);
            CHECK(mufu_op <= 8);
        }
    }
    // Simulate the lowered Maxwell instructions for several float inputs!
    for (float x : {-100.0f, -3.0f, -0.5f, -0.0f, 0.0f, 0.5f, 3.0f, 100.0f}) {
        std::array<u32, 256> r{};
        r[2] = std::bit_cast<u32>(x);
        r[255] = 0;
        for (u64 w : lowered.instructions) {
            const unsigned dst = w & 0xff, ra = (w >> 8) & 0xff, rb = (w >> 20) & 0xff;
            if ((w >> 52) == 0x010) { // MOV32I (000000010000..., imm32 in bits 20..51)
                r[dst] = u32((w >> 20) & 0xffffffffULL);
            } else if ((w >> 58) == 0x01) { // LOP32I.AND (000001xx..., imm32 in bits 20..51)
                const u32 imm = u32((w >> 20) & 0xffffffffULL);
                r[dst] = r[ra] & imm;
            } else if ((w >> 56) == 0x1e) { // FMUL32I (00011110..., imm32 in bits 20..51)
                const float imm = std::bit_cast<float>(u32((w >> 20) & 0xffffffffULL));
                r[dst] = std::bit_cast<u32>(std::bit_cast<float>(r[ra]) * imm);
            } else if ((w >> 52) == 0x508) { // MUFU (Ex2 = 2, Rcp = 4)
                const unsigned mop = (w >> 20) & 0xf;
                const float v = std::bit_cast<float>(r[ra]);
                r[dst] = std::bit_cast<u32>(mop == 2 ? std::exp2(v) : 1.0f / v);
            } else if ((w >> 48) == 0x5c58) { // FADD
                const float a = std::bit_cast<float>(r[ra]);
                float b = std::bit_cast<float>(r[rb]);
                if ((w >> 45) & 1) b = -b;
                r[dst] = std::bit_cast<u32>(a + b);
            } else if ((w >> 48) == 0x5c68) { // FMUL
                r[dst] = std::bit_cast<u32>(std::bit_cast<float>(r[ra]) * std::bit_cast<float>(r[rb]));
            } else if ((w >> 52) == 0x5c4) { // LOP.OR (0x5c47..., op 1 in bits 41..42)
                r[dst] = r[ra] | r[rb];
            }
        }
        const float got = std::bit_cast<float>(r[4]);
        const float want = std::tanh(x);
        if (x == 0.0f) {
            CHECK(std::signbit(got) == std::signbit(x) && got == 0.0f);
        } else {
            CHECK(std::fabs(got - want) < 1e-5f);
        }
    }

    // ProgramCaptureState: CALL.REL.NOINC (0x7944) to a post-EXIT subroutine captures through RET (0x7950).
    Instruction call{}, bra_self{}, ret{};
    call.words = {0x00007944U, 0x00000020U, 0x00400000U, 0}; // target = index 0 + 1 + 2 = index 3
    bra_self.words = {0x00007947U, 0xfffffff0U, 0x0003ffffU, 0};
    ret.words = {0x00007950U, 0, 0, 0};
    const std::array sub_prog{call, make_exit(), bra_self, ret};
    ProgramCaptureState cap;
    CHECK(cap.Observe(sub_prog[0], 0) == ProgramCaptureState::Result::Continue);
    CHECK(cap.Observe(sub_prog[1], 1) == ProgramCaptureState::Result::Continue); // does NOT stop at EXIT because target=3
    CHECK(cap.Observe(sub_prog[2], 2) == ProgramCaptureState::Result::Continue);
    CHECK(cap.Observe(sub_prog[3], 3) == ProgramCaptureState::Result::Complete);

    // 0xb07 FRND.F32 cbuf + 0x927 ISBEWR no-op
    Instruction isbewr{}, frnd_cbuf{};
    bits(isbewr, 0, 12, 0x927);
    bits(isbewr, 12, 4, 7);
    bits(frnd_cbuf, 0, 12, 0xb07);
    bits(frnd_cbuf, 12, 4, 7);
    bits(frnd_cbuf, 16, 8, 6);
    bits(frnd_cbuf, 38, 16, 0x8c);
    bits(frnd_cbuf, 54, 5, 10);
    bits(frnd_cbuf, 75, 2, 2);
    bits(frnd_cbuf, 84, 2, 2);
    CHECK(bool(LowerToMaxwell(std::array{isbewr, frnd_cbuf, make_exit()}, false)));

    // 0xb60 TEX Array2D + LB + DC (5 operands packed 4+1 across Ra=R20..R23, Rb=R32)
    // and with AOFFI added (6 operands packed 4+2 across Ra=R20..R23, Rb=R32..R33).
    for (bool with_aoffi : {false, true}) {
        Instruction tex_shadow{};
        tex_shadow.words = {0x14167b60U, 0xa0801020U, 0x051e41ffU | (with_aoffi ? 0x1000U : 0U), 0x00014200U};
        const auto shadow_low = LowerToMaxwell(std::array{tex_shadow, make_exit()}, false);
        CHECK(bool(shadow_low));
        if (shadow_low) {
            std::array<unsigned, 256> copy_src{};
            for (u64 w : shadow_low.instructions) {
                if ((w >> 48) == 0x5c98) {
                    copy_src[w & 0xff] = unsigned((w >> 20) & 0xff);
                }
            }
            CHECK(copy_src[250] == 20 && copy_src[251] == 21 && copy_src[252] == 22);
            if (!with_aoffi) {
                CHECK(copy_src[246] == 23 && copy_src[247] == 32 && copy_src[248] == 0);
            } else {
                CHECK(copy_src[246] == 23 && copy_src[247] == 32 && copy_src[248] == 33);
            }
        }
    }
}

int main() {
    for (const unsigned dimension : {1u, 5u})
        for (const unsigned predicate : {0u, 7u, 8u})
            for (const bool p0 : {false, true}) {
                for (const unsigned high : {14u, 19u, 44u, 199u})
                    check_txd_routing(12, 7, high, dimension, predicate, p0);
                for (const unsigned high : {14u, 18u, 44u, 198u})
                    check_txd_routing(12, 15, high, dimension, predicate, p0);
                check_txd_routing(12, 3, 255, dimension, predicate, p0);
                check_txd_routing(13, 1, 255, dimension, predicate, p0);
            }
    CHECK(!lower_txd(12, 0, 255, 1, 7));
    CHECK(!lower_txd(12, 15, 19, 1, 7));
    CHECK(!lower_txd(12, 7, 248, 1, 7));
    CHECK(!lower_txd(12, 7, 247, 1, 7));  // reserved by the lowering's global scratch-register guard
    CHECK(!lower_txd(12, 7, 19, 2, 7));
    check_constant_load_offsets();
    check_tanh_and_capture();
    std::printf("native Ampere lowering: %u checks, %u failures\n", checks, failures);
    return failures != 0;
}
