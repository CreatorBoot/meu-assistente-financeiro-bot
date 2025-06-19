)
        return

    nome = args[0].capitalize()
    if nome not in dados.get("nomes", []):
        await update.message.reply_text(f"O nome '{nome}' não está cadastrado.")
        return

    try:
        valor = float(args[1].replace(",", "."))
    except ValueError:
        await update.message.reply_text("Valor inválido. Use números, exemplo: 50 ou 50,00")
        return

    categoria = " ".join(args[2:]).capitalize()

    data_hoje = hoje_str()
    if "gastos" not in dados:
        dados["gastos"] = {}
    if data_hoje not in dados["gastos"]:
        dados["gastos"][data_hoje] = {}
    if nome not in dados["gastos"][data_hoje]:
        dados["gastos"][data_hoje][nome] = []

    dados["gastos"][data_hoje][nome].append({"categoria": categoria, "valor": valor})
    salvar_dados(dados)

    await update.message.reply_text(
        f"Gasto registrado: {nome} gastou {formata_reais(valor)} com {categoria} hoje."
    )

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_hoje = hoje_str()
    texto = f"🧾 Relatório do dia – {data_hoje}\n\n"
    gastos_hoje = dados.get("gastos", {}).get(data_hoje, {})

    perfil = dados.get("perfil", "Solo")
    apelido = dados.get("apelido", "")

    if perfil == "Solo":
        nome = dados["nomes"][0]
        total = soma_gastos_por_pessoa(gastos_hoje, nome)
        resumo = detalha_gastos(gastos_hoje, nome)
        texto += f"Você gastou {formata_reais(total)} hoje.\nAqui está o resumo detalhado:\n{resumo}"
    else:
        texto += f"📛 Grupo: {apelido}\n\n"
        total_geral = 0
        for nome in dados["nomes"]:
            total_nome = soma_gastos_por_pessoa(gastos_hoje, nome)
            resumo_nome = detalha_gastos(gastos_hoje, nome)
            texto += f"👤 {nome} gastou {formata_reais(total_nome)} hoje:\n{resumo_nome}\n\n"
            total_geral += total_nome
        texto += f"📊 Total do grupo: {formata_reais(total_geral)}"

    await update.message.reply_text(texto)

async def relatorio_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = datetime.now()
    inicio_semana = hoje - timedelta(days=hoje.weekday())

    perfil = dados.get("perfil", "Solo")
    apelido = dados.get("apelido", "")

    texto = f"📈 Relatório Semanal – {inicio_semana.strftime('%d/%m')} a {hoje.strftime('%d/%m')}\n"
    if perfil != "Solo":
        texto += f"📛 Grupo: {apelido}\n\n"

    total_geral = 0
    totais_pessoas = defaultdict(float)

    for i in range(0, (hoje - inicio_semana).days + 1):
        dia = (inicio_semana + timedelta(days=i)).strftime("%Y-%m-%d")
        gastos_dia = dados.get("gastos", {}).get(dia, {})
        for nome in dados.get("nomes", []):
            total_dia = soma_gastos_por_pessoa(gastos_dia, nome)
            totais_pessoas[nome] += total_dia
            total_geral += total_dia

    if perfil == "Solo":
        nome = dados.get("nomes", [None])[0]
        total = totais_pessoas[nome]
        texto += f"Nesta semana, você gastou um total de {formata_reais(total)}.\n"
    else:
        texto += "Gastos da semana por pessoa:\n\n"
        for nome in dados["nomes"]:
            texto += f"👤 {nome}: {formata_reais(totais_pessoas[nome])}\n"
        texto += f"\n💵 Total: {formata_reais(total_geral)}"

    await update.message.reply_text(texto)

async def relatorio_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hoje = datetime.now()
    inicio_mes = hoje.replace(day=1)

    perfil = dados.get("perfil", "Solo")
    apelido = dados.get("apelido", "")

    texto = f"📊 Relatório Mensal – {inicio_mes.strftime('%d/%m')} a {hoje.strftime('%d/%m')}\n"
    if perfil != "Solo":
        texto += f"📛 Grupo: {apelido}\n\n"

    total_geral = 0
    totais_pessoas = defaultdict(float)

    for i in range(0, (hoje - inicio_mes).days + 1):
        dia = (inicio_mes + timedelta(days=i)).strftime("%Y-%m-%d")
        gastos_dia = dados.get("gastos", {}).get(dia, {})
        for nome in dados.get("nomes", []):
            total_dia = soma_gastos_por_pessoa(gastos_dia, nome)
            totais_pessoas[nome] += total_dia
            total_geral += total_dia

    if perfil == "Solo":
        nome = dados.get("nomes", [None])[0]
        total = totais_pessoas[nome]
        texto += f"Neste mês, você gastou um total de {formata_reais(total)}.\n"
    else:
        texto += "Gastos do mês por pessoa:\n\n"
        for nome in dados["nomes"]:
            texto += f"👤 {nome}: {formata_reais(totais_pessoas[nome])}\n"
        texto += f"\n💵 Total: {formata_reais(total_geral)}"

    await update.message.reply_text(texto)

# =================== MAIN =====================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("registrar", registrar))
    app.add_handler(CommandHandler("relatorio", relatorio))
    app.add_handler(CommandHandler("relatorio_semanal", relatorio_semanal))
    app.add_handler(CommandHandler("relatorio_mensal", relatorio_mensal))

    app.run_polling()

if __name__ == "__main__":
    main()
