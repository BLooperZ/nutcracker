for %%i in (.\ROOMS\ROOM_*) do (
    python -m nutcracker.sputm.room %%i
)
