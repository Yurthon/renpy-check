# a clean file: every check must stay quiet on this one
define e = Character("Eileen")
define CFG_SPEED = 30
define 100 gui.text_size = 30
init -5 python:
    HELLO = "hi"
init python:
    def helper(x):
        return x + 1
label start:
    e "Hello, 100%% sure."
    "Narration is fine."
    jump start_2
label start_2:
    call screen demo
    return
screen demo():
    frame:
        xanchor 1.0
        xpos 100
        textbutton "ok" action Return()
    text "a" size 20 xalign 0.5
    text ("b" if True
          else "c") size 20
