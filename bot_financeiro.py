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

# Pega o token do Telegram da variável de ambiente
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Habilita logs para debug
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============== ESTADOS DA CONVERSA ===============
(
    STATE_CADASTRO_TIPO,
    STATE_CADASTRO_NOMES,
    STATE_CADASTRO_APELIDO,
    STATE_CADASTRO_RENDAS,
    STATE_CADASTRO_FIXOS,
    STATE_REGISTRAR_GASTO,
    STATE_EMPRESTIMO_OPCOES,
    STATE_REGISTRAR_EMPRESTIMO,
    STATE_REGISTRAR_PAGAMENTO,
    STATE_BONIFICACAO,
) = range(10)

# =============== ARMAZENAMENTO SIMPLES EM JSON ===============
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

# =============== DADOS GLOBAIS EM MEMÓRIA ===============
dados = carregar_dados()

# =================== HELPERS =====================

def hoje_str():
    return datetime.now().strftime("%Y-%m-%d")

def formata_reais(valor):
    return f"R$ {valor:.2f}".replace(".", ",")

def soma_gastos_por_pessoa(data_gastos, nome):
    total = 0
    for gasto in data_gastos.get(nome, []):
        total += gasto["valor"]
    return total

def detalha_gastos(data_gastos, nome):
    resumo = defaultdict(float)
    for gasto in data_gastos.get(nome, []):
        resumo[gasto["categoria"]] += gasto["valor"]
    linhas = []
    for categoria, valor in resumo.items():
        linhas.append(f"{categoria}: {formata_reais(valor)}")
    return "\n".join(linhas) if linhas else "Sem gastos registrados."

def verifica_perfil_valido():
    return dados.get("perfil") in ["Solo", "Casal", "Família"]

# =================== HANDLERS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if verifica_perfil_valido():
        await update.message.reply_text(
            f"Olá {dados.get('apelido', '')}! Seu assistente financeiro está pronto. "
            "Você pode registrar gastos, pedir relatórios e usar outras funções.\n\n"
            "Digite /ajuda para ver comandos disponíveis."
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Oi! Eu sou seu assistente financeiro pessoal, pronto para ajudar a controlar seus gastos.\n\n"
            "Primeiro, preciso saber: você vai usar este assistente sozinho, em casal ou em família?\n"
            "Responda com: Solo, Casal ou Família."
        )
        return STATE_CADASTRO_TIPO

async def cadastro_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().lower()
    if texto not in ["solo", "casal", "família", "familia"]:
        await update.message.reply_text(
            "Por favor, responda apenas com: Solo, Casal ou Família."
        )
        return STATE_CADASTRO_TIPO

    perfil = texto.capitalize() if texto != "familia" else "Família"
    dados["perfil"] = perfil
    salvar_dados(dados)

    await update.message.reply_text(
        f"Ótimo, perfil '{perfil}' selecionado.\n"
        "Agora me diga o nome das pessoas que vão usar o assistente, separados por vírgula.\n\n"
        "Exemplo: Bruno, Camila\nSe for solo, apenas seu nome."
    )
    return STATE_CADASTRO_NOMES

async def cadastro_nomes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    nomes = [nome.strip() for nome in texto.split(",") if nome.strip()]
    if len(nomes) == 0:
        await update.message.reply_text("Por favor, envie pelo menos um nome válido.")
        return STATE_CADASTRO_NOMES

    dados["nomes"] = nomes
    salvar_dados(dados)

    await update.message.reply_text(
        "Beleza! Agora envie um apelido especial para o grupo — pode ser o nome do casal, família ou algo divertido.\n\n"
        "Exemplo: Família Silva, Casal do Barulho, Time da Economia"
    )
    return STATE_CADASTRO_APELIDO

async def cadastro_apelido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if not texto:
        await update.message.reply_text("Por favor, envie um apelido válido.")
        return STATE_CADASTRO_APELIDO

    dados["apelido"] = texto
    salvar_dados(dados)

    await update.message.reply_text(
        "Agora, para ajudar no planejamento, me diga a renda mensal de cada um.\n"
        "Envie no formato:\nBruno: 3500\nCamila: 2500\n\nSe for só você, apenas seu salário."
    )
    return STATE_CADASTRO_RENDAS

async def cadastro_rendas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    linhas = texto.split("\n")
    rendas = {}
    for linha in linhas:
        if ":" not in linha:
            continue
        nome, valor = linha.split(":", 1)
        nome = nome.strip()
        valor = valor.strip().replace("R$", "").replace(",", ".")
        try:
            valor_float = float(valor)
            if nome not in dados.get("nomes", []):
                await update.message.reply_text(f"O nome '{nome}' não está cadastrado no grupo. Por favor, envie as rendas corretamente.")
                return STATE_CADASTRO_RENDAS
            rendas[nome] = valor_float
        except ValueError:
            await update.message.reply_text(f"Valor inválido para {nome}. Tente novamente.")
            return STATE_CADASTRO_RENDAS

    if len(rendas) == 0:
        await update.message.reply_text("Não consegui ler nenhuma renda válida. Tente novamente.")
        return STATE_CADASTRO_RENDAS

    dados["rendas"] = rendas
    salvar_dados(dados)

    await update.message.reply_text(
        "Ótimo! Agora me envie os gastos fixos mensais que você costuma pagar.\n"
        "Por exemplo:\n"
        "💡 Luz: 170\n"
        "💧 Água: 90\n"
        "🌐 Internet: 120\n"
        "🏋️‍♀️ Academia: 100\n"
        "🎬 Streaming: Netflix (39,90), Prime Video (14,90)\n\n"
        "Você pode enviar tudo junto ou uma linha por vez."
    )
    return STATE_CADASTRO_FIXOS

async def cadastro_fixos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()

    fixos = dados.get("fixos", {})
    linhas = texto.split("\n")
    for linha in linhas:
        if ":" not in linha:
            continue
        chave, valor = linha.split(":", 1)
        chave = chave.strip()
        valor = valor.strip()
        if chave.lower() == "streaming":
            streaming_ = {}
            partes = valor.split(",")
            for parte in partes:
                if "(" in parte and ")" in parte:
                    nome_stream = parte.split("(")[0].strip()
                    valor_stream = parte.split("(")[1].replace(")", "").replace("R$", "").replace(",", ".").strip()
                    try:
                        valor_float = float(valor_stream)
                        streaming_[nome_stream] = valor_float
                    except:
                        continue
            fixos["Streaming"] = streaming_
        else:
            try:
                valor_float = float(valor.replace("R$", "").replace(",", "."))
                fixos[chave] = valor_float
            except:
                continue

    dados["fixos"] = fixos
    salvar_dados(dados)

    await update.message.reply_text(
        "Perfeito! Cadastro finalizado. Agora você pode registrar seus gastos escrevendo algo como:\n"
        "→ 'Gastei 40 no mercado'\n"
        "→ 'Camila: 25 em Uber'\n"
        "→ 'Bruno gastou 30 com padaria'\n\n"
        "Use /relatorio para ver seus relatórios.\n"
        "Se precisar de ajuda, digite /ajuda."
    )
    return ConversationHandler.END

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "Comandos disponíveis:\n"
        "/start - Começar ou reiniciar cadastro\n"
        "/ajuda - Mostrar esta mensagem\n"
        "/relatorio - Gerar relatório do dia atual\n"
        "/relatorio_semanal - Gerar relatório da semana\n"
        "/relatorio_mensal - Gerar relatório do mês\n"
        "/registrar - Registrar um gasto (exemplo: /registrar Camila 50 Uber)\n"
        "/emprestimos - Gerenciar empréstimos e pagamentos\n"
    )
    await update.message.reply_text(texto)

async def registrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Uso correto: /registrar Nome Valor Categoria\nExemplo: /registrar Camila 50 Mercado"
