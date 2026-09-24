label c03_start:
    jump nowhere
label c03_t:
    "x"
    call screen ghost
    $ renpy.notify("x")
    return
screen s2():
    textbutton "go" action Jump("nowhere2")
