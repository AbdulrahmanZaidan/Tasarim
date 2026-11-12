; rt_c.asm: tdcc'nin runtime.asm'ye ek olarak kullandığı yardımcılar.
; runtime.asm ile birlikte .include edilir (onun sembollerini kullanır).
;
;   __shl16   __rv <<= __cnt              (mantıksal)
;   __shr16   __rv >>= __cnt              (mantıksal, unsigned)
;   __asr16   __rv >>= __cnt              (aritmetik, int)
;   __sdiv16  işaretli bölme: __rv = __div_n / __div_d, __div_r = __div_n % __div_d
;             (C kuralı: bölüm sıfıra doğru kesilir, kalan bölünenin işaretini alır)
; A ve flag'ler bozulur.

__sgn_q  = $801A        ; 1  bölümün işareti (b7)
__sgn_r  = $801B        ; 1  kalanın işareti (b7)

__shl16:
        LDA __cnt
        TST
        BEQ shl16_son
shl16_tur:
        LDA __rv
        SHL
        STA __rv
        LDA __rv+1
        ROL
        STA __rv+1
        LDA __cnt
        DEC
        STA __cnt
        BNE shl16_tur
shl16_son:
        RET

__shr16:
        LDA __cnt
        TST
        BEQ shr16_son
shr16_tur:
        LDA __rv+1
        SHR
        STA __rv+1
        LDA __rv
        ROR
        STA __rv
        LDA __cnt
        DEC
        STA __cnt
        BNE shr16_tur
shr16_son:
        RET

__asr16:
        LDA __cnt
        TST
        BEQ asr16_son
asr16_tur:
        LDA __rv+1
        ASR
        STA __rv+1
        LDA __rv
        ROR
        STA __rv
        LDA __cnt
        DEC
        STA __cnt
        BNE asr16_tur
asr16_son:
        RET

__sdiv16:
        LDA __div_n+1
        STA __sgn_r
        XOR __div_d+1
        STA __sgn_q
        LDA __div_n+1           ; bölünen negatifse mutlak değeri
        TST
        BPL sdiv_n_pos
        LDA #0
        SUB __div_n
        STA __div_n
        LDA #0
        SBC __div_n+1
        STA __div_n+1
sdiv_n_pos:
        LDA __div_d+1           ; bölen negatifse mutlak değeri
        TST
        BPL sdiv_d_pos
        LDA #0
        SUB __div_d
        STA __div_d
        LDA #0
        SBC __div_d+1
        STA __div_d+1
sdiv_d_pos:
        CALL __divmod16
        LDA __sgn_q
        TST
        BPL sdiv_q_pos
        LDA #0
        SUB __rv
        STA __rv
        LDA #0
        SBC __rv+1
        STA __rv+1
sdiv_q_pos:
        LDA __sgn_r
        TST
        BPL sdiv_r_pos
        LDA #0
        SUB __div_r
        STA __div_r
        LDA #0
        SBC __div_r+1
        STA __div_r+1
sdiv_r_pos:
        RET
