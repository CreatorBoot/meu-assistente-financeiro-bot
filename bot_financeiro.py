import os
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ====== CONFIGURAÇÕES BÁSICAS ======
TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====== ESTADOS DA CONVERSA ======
(
    STATE_CADASTRO_TIPO,
    STATE_CADASTRO_NOMES,
    STATE_CADASTRO_APELIDO,
    STATE_CADASTRO_RENDAS,
    STATE_CADASTRO_FIXOS,
) = range(5)

# ====== ARQUIVO DE DADOS ======
DATA_FILE = "dados_assistente.json"

def carregar_dados():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def salvar_dados(dados):
    with open(DATA_FILE, "w") as f:
        json.dump(dados, f, indent=2)

dados = carregar_dados()

# ====== FUNÇÕES AUXILIARES ======
def hoje_str():
    return datetime.now().strftime("%Y-%m-%d")

def formata_reais(valor):
    return f"R$ {valor:.2f}".replace(".", ",")

def soma_gastos_por_pessoa(data_gastos, nome):
    return sum(g["valor"] for g in data_gastos.get(nome, []))

def detalha_gastos(data_gastos, nome):
    resumo = defaultdict(float)
    for gasto in data_gastos.get(nome, []):
        resumo[gasto["categoria"]] += gasto["valor"]
    return "\n".join(f"{cat}: {formata_reais(val)}" for cat, val in resumo.items()) or "Sem gastos registrados."

def verifica_perfil_valido():
    return dados.get("perfil") in ["Solo", "Casal", "Família"]

# ====== HANDLERS DE CONVERSA ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if verifica_perfil_valido():
        await update.message.reply_text(
            f"Olá {dados.get('apelido', '')}! Seu assistente financeiro está pronto. "
            "Você pode registrar gastos, pedir relatórios e usar outras funções.\n\nDigite /ajuda para ver comandos disponíveis."
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Oi! Eu sou seu assistente financeiro.\nVocê vai usar este assistente sozinho, em casal ou em família?\n\nResponda com: Solo, Casal ou Família."
        )
        return STATE_CADASTRO_TIPO

async def cadastro_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    perfil = update.message.text.strip().capitalize()
    if perfil not in ["Solo", "Casal", "Família"]:
        await update.message.reply_text("Por favor, responda apenas com: Solo, Casal ou Família.")
        return STATE_CADASTRO_TIPO
    dados["perfil"] = perfil
    salvar_dados(dados)
    await update.message.reply_text("Agora me diga os nomes separados por vírgula.\nExemplo: Bruno, Camila")
    return STATE_CADASTRO_NOMES

async def cadastro_nomes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nomes = [n.strip() for n in update.message.text.split(",") if n.strip()]
    if not nomes:
        await update.message.reply_text("Envie ao menos um nome válido.")
        return STATE_CADASTRO_NOMES
    dados["nomes"] = nomes
    salvar_dados(dados)
    await update.message.reply_text("Agora envie um apelido pro grupo (ex: Família Silva).")
    return STATE_CADASTRO_APELIDO

async def cadastro_apelido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    apelido = update.message.text.strip()
    if not apelido:
        await update.message.reply_text("Envie um apelido válido.")
        return STATE_CADASTRO_APELIDO
    dados["apelido"] = apelido
    salvar_dados(dados)
    await update.message.reply_text("Agora envie a renda de cada pessoa:\nExemplo:\nBruno: 3500\nCamila: 2500")
    return STATE_CADASTRO_RENDAS

async def cadastro_rendas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    linhas = update.message.text.strip().split("\n")
    rendas = {}
    for linha in linhas:
        if ":" in linha:
            nome, valor = linha.split(":", 1)
            try:
                nome = nome.strip()
                valor_float = float(valor.strip().replace("R$", "").replace(",", "."))
                if nome not in dados.get("nomes", []):
                    await update.message.reply_text(f"O nome '{nome}' não foi cadastrado.")
                    return STATE_CADASTRO_RENDAS
                rendas[nome] = valor_float
            except ValueError:
                await update.message.reply_text(f"Valor inválido para {nome}.")
                return STATE_CADASTRO_RENDAS
    dados["rendas"] = rendas
    salvar_dados(dados)
    await update.message.reply_text("Agora envie os gastos fixos mensais no formato:\nLuz: 120\nÁgua: 90")
    return STATE_CADASTRO_FIXOS

async def cadastro_fixos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fixos = {}
    for linha in update.message.text.strip().split("\n"):
        if ":" in linha:
            nome, valor = linha.split(":", 1)
            try:
                fixos[nome.strip()] = float(valor.strip().replace("R$", "").replace(",", "."))
            except:
                continue
    dados["fixos"] = fixos
    salvar_dados(dados)
    await update.message.reply_text("Cadastro finalizado! Você pode registrar gastos com /registrar.\nDigite /ajuda para comandos.")
    return ConversationHandler.END

# ====== COMANDOS PRINCIPAIS ======
async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponíveis:\n"
        "/start - Iniciar ou reiniciar cadastro\n"
        "/ajuda - Ver esta ajuda\n"
        "/registrar - Registrar um gasto (/registrar Nome 30 Mercado)\n"
        "/relatorio - Relatório de hoje\n"
        "/relatorio_semanal - Relatório da semana\n"
        "/relatorio_mensal - Relatório do mês"
    )

async def registrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Uso correto: /registrar Nome Valor Categoria")
        return
    nome = args[0].capitalize()
    if nome not in dados.get("nomes", []):
        await update.message.reply_text("Nome não encontrado.")
        return
    try:
        valor = float(args[1].replace(",", "."))
    except:
        await update.message.reply_text("Valor inválido.")
        return
    categoria = " ".join(args[2:]).capitalize()
    hoje = hoje_str()
    dados.setdefault("gastos", {}).setdefault(hoje, {}).setdefault(nome, []).append(
        {"categoria": categoria, "valor": valor}
    )
    salvar_dados(dados)
    await update.message.reply_text(f"{nome} gastou {formata_reais(valor)} com {categoria}.")

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = hoje_str()
    gastos = dados.get("gastos", {}).get(data, {})
    texto = f"🧾 Relatório de {data}:\n\n"
    total_geral = 0
    for nome in dados.get("nomes", []):
        total = soma_gastos_por_pessoa(gastos, nome)
        total_geral += total
        texto += f"👤 {nome}: {formata_reais(total)}\n{detalha_gastos(gastos, nome)}\n\n"
    texto += f"💰 Total geral: {formata_reais(total_geral)}"
    await update.message.reply_text(texto)

async def relatorio_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = datetime.now()
    inicio = hoje - timedelta(days=hoje.weekday())
    texto = f"📊 Relatório da semana ({inicio.strftime('%d/%m')} a {hoje.strftime('%d/%m')}):\n\n"
    total_geral = 0
    totais = defaultdict(float)
    for i in range(7):
        dia = (inicio + timedelta(days=i)).strftime("%Y-%m-%d")
        gastos_dia = dados.get("gastos", {}).get(dia, {})
        for nome in dados.get("nomes", []):
            totais[nome] += soma_gastos_por_pessoa(gastos_dia, nome)
            total_geral += soma_gastos_por_pessoa(gastos_dia, nome)
    for nome in dados.get("nomes", []):
        texto += f"👤 {nome}: {formata_reais(totais[nome])}\n"
    texto += f"\n💰 Total: {formata_reais(total_geral)}"
    await update.message.reply_text(texto)

async def relatorio_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = datetime.now()
    texto = f"📆 Relatório mensal ({hoje.strftime('%m/%Y')}):\n\n"
    totais = defaultdict(float)
    total_geral = 0
    for data, gastos_dia in dados.get("gastos", {}).items():
        if data.startswith(hoje.strftime("%Y-%m")):
            for nome in dados.get("nomes", []):
                totais[nome] += soma_gastos_por_pessoa(gastos_dia, nome)
                total_geral += soma_gastos_por_pessoa(gastos_dia, nome)
    for nome in dados.get("nomes", []):
        texto += f"👤 {nome}: {formata_reais(totais[nome])}\n"
    texto += f"\n💰 Total: {formata_reais(total_geral)}"
    await update.message.reply_text(texto)

# ====== INICIALIZAÇÃO DO BOT ======
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conversa = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STATE_CADASTRO_TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, cadastro_tipo)],
            STATE_CADASTRO_NOMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, cadastro_nomes)],
            STATE_CADASTRO_APELIDO: [MessageHandler(filters.TEXT & ~filters.COMMAND, cadastro_apelido)],
            STATE_CADASTRO_RENDAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cadastro_rendas)],
            STATE_CADASTRO_FIXOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cadastro_fixos)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conversa)
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("registrar", registrar))
    app.add_handler(CommandHandler("relatorio", relatorio))
    app.add_handler(CommandHandler("relatorio_semanal", relatorio_semanal))
    app.add_handler(CommandHandler("relatorio_mensal", relatorio_mensal))

    app.run_polling()
