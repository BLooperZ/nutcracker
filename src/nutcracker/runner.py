import typer

from nutcracker.smush import runner as smush

app = typer.Typer()
app.add_typer(smush.app, name='smush')

if __name__ == "__main__":
    app()
