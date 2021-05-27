import typer

from nutcracker.smush import runner as smush
from nutcracker.sputm import runner as sputm

app = typer.Typer()
app.add_typer(smush.app, name='smush')
app.add_typer(sputm.app, name='sputm')

if __name__ == "__main__":
    app()
