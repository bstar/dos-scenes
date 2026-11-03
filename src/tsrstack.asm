; Preserve the caller's interrupt stack and run scene code on private DGROUP SS.
.8086
.model large,c
extrn ds_saved_ss:word, ds_saved_sp:word
extrn ds_private_stack:byte
extrn ds_resident_run:far
.code
public ds_private_call
ds_private_call proc far
    pushf
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    cli
    mov ax,seg ds_saved_ss
    mov ds,ax
    mov ds_saved_ss,ss
    mov ds_saved_sp,sp
    mov ss,ax
    mov sp,offset ds_private_stack+8192
    sti
    call ds_resident_run
    cli
    mov ax,seg ds_saved_ss
    mov ds,ax
    mov ax,ds_saved_ss
    mov ss,ax
    mov sp,ds_saved_sp
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    popf
    retf
ds_private_call endp
end
