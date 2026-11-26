from . import aliexpress, kabum

# Para adicionar uma loja: crie um módulo com buscar(termo) -> lista de ofertas
# (mesmo formato do kabum.py) e registre aqui.
LOJAS = {"kabum": kabum, "aliexpress": aliexpress}
