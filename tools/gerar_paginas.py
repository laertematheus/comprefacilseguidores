#!/usr/bin/env python3
"""Gera as páginas de SEO do CompreFácil Seguidores.

Lê data/catalogo_precos.csv (fora do git: tem o custo do BRSMM) e escreve, na raiz do site:
  - uma página por serviço (plataforma x tipo), por intenção (brasileiros, reais, baratos) e por guia;
  - os hubs /servicos/ e /guia/, o placeholder /painel/, sitemap.xml e robots.txt.

As páginas publicam só o preço de venda. Rode de novo sempre que o catálogo mudar:
    python3 tools/gerar_paginas.py
"""
import csv
import datetime
import html
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://laertematheus.github.io/comprefacilseguidores/"  # trocar pelo domínio próprio quando existir
CATALOG = ROOT / "data" / "catalogo_precos.csv"
TODAY = datetime.date.today()
YEAR = TODAY.year
BRAND = "CompreFácil Seguidores"
# muda a cada geração: força o navegador a baixar o CSS novo depois de um deploy
CSS_VERSION = datetime.datetime.now().strftime("%Y%m%d%H%M")

# ----------------------------------------------------------------------------- catálogo

def load_catalog():
    rows = []
    with open(CATALOG, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": r["id"],
                "name": r["servico"],
                "cat": r["categoria"],
                "rate": float(r["venda_1k"]),
                "min": int(r["min"] or 0),
                "max": int(r["max"] or 0),
                "br": r["br"] == "True",
                "refill": int(r["reposicao_dias"] or 0),
                "time": r["tempo_medio"],
            })
    return rows

CAT = load_catalog()
BY_ID = {r["id"]: r for r in CAT}


def quality(name):
    if re.search(r"alta qualidade|qualidade real|premium|reais e ativos", name, re.I):
        return 0
    if re.search(r"m[ée]dia", name, re.I):
        return 1
    return 2


def pick(plat_rx=None, name_rx=None, fixed=None, exclude=None, prefer_br=True):
    """Escolhe o serviço padrão da página: BR com reposição > BR > com reposição > qualquer;
    dentro do grupo, qualidade alta/média antes de baixa, e o mais barato."""
    if fixed:
        return BY_ID[str(fixed)]
    xs = [r for r in CAT
          if re.search(plat_rx, (r["name"] + " " + r["cat"]).lower())
          and re.search(name_rx, r["name"].lower())
          and not (exclude and re.search(exclude, r["name"].lower()))
          and r["max"] >= 1000]
    if not xs:
        raise SystemExit(f"nenhum serviço para {plat_rx} / {name_rx}")

    def tier(r):
        if prefer_br:
            return 0 if r["br"] and r["refill"] else 1 if r["br"] else 2 if r["refill"] else 3
        return 0 if r["refill"] else 1
    return min(xs, key=lambda r: (tier(r), 0 if quality(r["name"]) <= 1 else 1, r["rate"]))


CANDS = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000]
MIN_TICKET = 4.90


def ceil90(v):
    """Arredonda para cima no próximo ',90' (nunca abaixo da margem)."""
    f = math.floor(v)
    return f + 0.9 if v - f <= 0.9 + 1e-9 else f + 1.9


def price_for(svc, qty):
    return max(MIN_TICKET, ceil90(qty / 1000 * svc["rate"]))


def packages(svc, n=4):
    valid = [q for q in CANDS if svc["min"] <= q <= svc["max"]]
    start = next((i for i, q in enumerate(valid) if qty_raw(svc, q) >= 2.5), max(len(valid) - n, 0))
    picked = [valid[i] for i in range(start, len(valid), 2)][:n]
    if len(picked) < n:  # completa com os vizinhos quando o limite máximo é baixo
        extra = [q for q in valid[start:] if q not in picked]
        picked = sorted(picked + extra[: n - len(picked)])
    return [{"qty": q, "price": price_for(svc, q)} for q in picked]


def qty_raw(svc, q):
    return q / 1000 * svc["rate"]

# ----------------------------------------------------------------------------- formatação

def brl(v):
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def num(n):
    return f"{n:,}".replace(",", ".")


def esc(s):
    return html.escape(s, quote=True)


def refill_txt(svc):
    d = svc["refill"]
    if not d:
        return "Sem reposição"
    if d >= 999:
        return "Reposição vitalícia"
    return f"Reposição de {d} dia{'s' if d > 1 else ''}"


def time_txt(svc):
    t = svc["time"].strip()
    if not t:
        return ""
    parts = t.split()
    return " ".join(parts[:2])


def tokens(svc, unit):
    return {
        "preco_min": brl(packages(svc)[0]["price"]) if svc else "",
        "preco_mil": brl(price_for(svc, 1000)) if svc else "",
        "origem": "Brasileiros" if svc and svc["br"] else "Internacionais",
        "origem_l": "brasileiros" if svc and svc["br"] else "internacionais",
        "reposicao": refill_txt(svc) if svc else "",
        "reposicao_l": refill_txt(svc).lower() if svc else "",
        "tempo": time_txt(svc) if svc else "",
        "unit": unit,
        "ano": YEAR,
    }

# ----------------------------------------------------------------------------- conteúdo: serviços
# Cada página tem texto próprio. Tokens entre chaves vêm do serviço escolhido no catálogo.

IG = r"instagram"
SERVICES = [
    dict(
        slug="comprar-seguidores-instagram", plat="Instagram", icon="ig", quiz="Instagram",
        svc=dict(fixed=3016), unit="seguidores",
        title="Comprar Seguidores Instagram Brasileiros | a partir de {preco_min}",
        desc="Seguidores brasileiros no Instagram a partir de {preco_min}, sem senha, com entrega gradual e {reposicao_l}. Pagamento via PIX e plano em 1 minuto.",
        h1="Comprar seguidores no Instagram, brasileiros e do seu nicho",
        lead="Seguidores reais do Brasil, entregues aos poucos no seu @ público. Você escolhe o público e o ritmo, paga no PIX e acompanha tudo pelo painel.",
        intro=[
            "No Instagram, o número de seguidores é a primeira coisa que alguém vê no seu perfil, antes da bio e antes do conteúdo. Um perfil pequeno parece recém-criado mesmo quando o trabalho por trás é bom, e isso afasta quem chega pela primeira vez.",
            "Comprar seguidores brasileiros resolve essa primeira impressão e dá ao algoritmo um sinal de que o perfil merece ser mostrado para mais gente. Aqui você escolhe o público (mulheres, homens ou ambos), o nicho e a velocidade da entrega. Os seguidores chegam aos poucos, sem que a gente peça sua senha.",
        ],
        why=[
            ("target", "Público que combina com você", "Escolha entre seguidoras, seguidores ou ambos. Um perfil de moda recebe gente de moda, não contas aleatórias."),
            ("plant", "Entrega que parece natural", "Os seguidores chegam ao longo de horas ou dias, sem picos que chamem a atenção do Instagram."),
            ("refresh", "{reposicao}", "Se houver queda dentro do prazo, você pede reposição pelo painel, sem custo."),
        ],
        faq=[
            ("Comprar seguidores no Instagram é seguro?", "É, quando a entrega é gradual e ninguém pede a sua senha. A gente usa só o seu @ público. O que costuma gerar bloqueio são serviços que pedem login ou despejam milhares de seguidores de uma vez, por isso a opção recomendada é a entrega aos poucos."),
            ("Os seguidores são brasileiros de verdade?", "Sim. Este serviço entrega perfis brasileiros, e você ainda escolhe o gênero predominante. Perfis internacionais custam menos, mas interagem pouco com conteúdo em português."),
            ("Quanto custam 1.000 seguidores no Instagram?", "Hoje, {preco_mil} por 1.000 seguidores brasileiros com público misto. Seguidoras ou seguidores de um gênero só custam um pouco mais. O valor exato aparece no fim do questionário, antes do pagamento."),
            ("Meu perfil precisa estar público?", "Sim, durante a entrega. Perfis privados não recebem seguidores novos automaticamente. Quando o pedido terminar, você pode voltar a fechar o perfil."),
            ("Posso escolher o nicho dos seguidores?", "Pode. No questionário você diz sobre o que é o seu conteúdo e de qual nicho quer os novos seguidores. Seguidores do mesmo nicho tendem a curtir e comentar mais."),
        ],
        related=["comprar-curtidas-instagram", "comprar-visualizacoes-instagram", "comprar-comentarios-instagram", "comprar-seguidores-brasileiros", "comprar-seguidores-tiktok", "guia/vale-a-pena-comprar-seguidores"],
    ),
    dict(
        slug="comprar-seguidores-tiktok", plat="TikTok", icon="tt", quiz="TikTok",
        svc=dict(fixed=3828), unit="seguidores",
        title="Comprar Seguidores TikTok Brasileiros | a partir de {preco_min}",
        desc="Seguidores brasileiros no TikTok a partir de {preco_min}, com {reposicao_l} e entrega no ritmo que você escolher. Sem senha, pagamento via PIX.",
        h1="Comprar seguidores no TikTok, brasileiros e com reposição",
        lead="Mais credibilidade para o seu perfil e acesso mais rápido a recursos como lives e TikTok Shop. Só o @, nada de senha.",
        intro=[
            "No TikTok, os seguidores pesam menos no alcance do que no Instagram: a página Para Você mostra vídeos para quem ainda não te segue. Mas eles pesam muito em credibilidade e no acesso a recursos. Lives e o TikTok Shop costumam exigir um número mínimo de seguidores, e marcas olham esse número antes de fechar uma publi.",
            "Os seguidores deste serviço são {origem_l}, chegam aos poucos e contam com {reposicao_l}. Você informa só o @ do perfil.",
        ],
        why=[
            ("bolt", "Destrave recursos da plataforma", "Chegar ao mínimo de seguidores exigido para lives e vendas deixa de depender só de viralizar."),
            ("users", "Seguidores {origem_l}", "Perfis que entendem o idioma dos seus vídeos e combinam com o seu público."),
            ("refresh", "{reposicao}", "Se alguém deixar de seguir dentro do prazo, a gente repõe pelo painel."),
        ],
        faq=[
            ("Comprar seguidores no TikTok dá shadowban?", "O risco aparece quando a entrega é artificial demais: milhares de contas de uma vez, perfis sem foto, países aleatórios. Com seguidores brasileiros e entrega gradual, o crescimento fica parecido com o de um vídeo que performou bem."),
            ("Quantos seguidores preciso para fazer live no TikTok?", "O TikTok costuma liberar lives a partir de 1.000 seguidores para maiores de 18 anos, mas a regra muda de tempos em tempos. Confira o requisito atual no app antes de montar sua meta."),
            ("Serve para TikTok Shop?", "Serve. Lojas com mais seguidores passam mais confiança para quem está comprando pela primeira vez. Os seguidores entram no perfil normalmente, então valem para a loja vinculada a ele."),
            ("Quanto custam 1.000 seguidores no TikTok?", "Hoje, {preco_mil} por 1.000 seguidores {origem_l} com {reposicao_l}."),
        ],
        related=["comprar-visualizacoes-tiktok", "comprar-curtidas-tiktok", "comprar-seguidores-instagram", "comprar-seguidores-kwai", "comprar-seguidores-brasileiros", "guia/quanto-custa-1000-seguidores"],
    ),
    dict(
        slug="comprar-curtidas-instagram", plat="Instagram", icon="ig", quiz=None,
        svc=dict(plat_rx=IG, name_rx=r"curtida", exclude=r"coment"), unit="curtidas",
        title="Comprar Curtidas Instagram Brasileiras | a partir de {preco_min}",
        desc="Curtidas {origem_l} para posts e Reels do Instagram a partir de {preco_min}. Entrega rápida, sem senha e pagamento via PIX.",
        h1="Comprar curtidas no Instagram para posts e Reels",
        lead="Curtidas nos primeiros minutos fazem o algoritmo mostrar o post para mais gente. Você escolhe o post, a gente entrega.",
        intro=[
            "O Instagram decide até onde um post vai olhando para o que acontece logo depois da publicação. Um post que recebe curtidas cedo é testado para mais gente; um que fica parado some do feed em poucas horas.",
            "Com curtidas {origem_l}, o post começa com prova social: quem chega vê que outras pessoas já aprovaram o conteúdo. Você informa o link do post ou do Reels, e as curtidas chegam sem que a gente precise da sua senha.",
        ],
        why=[
            ("bolt", "Empurrão nos primeiros minutos", "É quando o algoritmo decide se o post merece mais alcance."),
            ("heart", "Prova social visível", "Posts com mais curtidas recebem mais curtidas de quem chega depois."),
            ("target", "Você escolhe o post", "Mande o link de qualquer post ou Reels público do seu perfil."),
        ],
        faq=[
            ("Posso escolher em qual post as curtidas vão?", "Pode. Cada pedido vai para um link: um post do feed, um carrossel ou um Reels. Para vários posts, basta fazer um pedido para cada link."),
            ("Comprar curtidas no Instagram dá ban?", "Curtidas são a interação mais comum do Instagram, e receber algumas centenas num post não é algo fora do normal. Sem pedido de senha e com o post público, o risco é baixo."),
            ("Quanto custam 1.000 curtidas no Instagram?", "Hoje, {preco_mil} por 1.000 curtidas {origem_l}. O menor pacote custa {preco_min}."),
            ("As curtidas somem depois?", "Parte delas pode cair com o tempo quando o Instagram faz limpeza de contas. {reposicao} neste serviço."),
        ],
        related=["comprar-seguidores-instagram", "comprar-visualizacoes-instagram", "comprar-comentarios-instagram", "comprar-curtidas-tiktok", "comprar-seguidores-reais", "guia/como-saber-se-seguidores-sao-reais"],
    ),
    dict(
        slug="comprar-inscritos-youtube", plat="YouTube", icon="yt", quiz="YouTube",
        svc=dict(fixed=2715), unit="inscritos",
        title="Comprar Inscritos YouTube com Reposição | a partir de {preco_min}",
        desc="Inscritos no YouTube a partir de {preco_min}, entrega gradual e {reposicao_l}. Sem senha, via PIX. Veja o que ajuda (e o que não) na monetização.",
        h1="Comprar inscritos no YouTube",
        lead="Inscritos entregues aos poucos, com {reposicao_l}. Antes de comprar, veja o que eles resolvem e o que não resolvem na monetização.",
        note="Os inscritos deste serviço vêm de perfis internacionais. Ainda não oferecemos inscritos brasileiros no YouTube com a qualidade e a reposição que a gente exige.",
        intro=[
            "Um canal com poucos inscritos perde espectadores antes mesmo do play: quem chega por uma busca olha o número abaixo do nome e decide se vale a pena assistir. Inscritos resolvem essa primeira impressão e ajudam o canal a parecer tão bom quanto o conteúdo que ele tem.",
            "Se o objetivo é monetizar, vale saber a regra inteira. O Programa de Parcerias do YouTube pede 1.000 inscritos e também 4.000 horas de exibição públicas nos últimos 12 meses (ou 10 milhões de visualizações em Shorts em 90 dias), e o canal passa por uma revisão manual. Inscritos ajudam com a primeira parte; nenhum serviço consegue garantir a aprovação.",
        ],
        why=[
            ("users", "Primeira impressão de canal grande", "O número de inscritos aparece em toda busca, sugestão e página do canal."),
            ("plant", "Entrega gradual", "Os inscritos chegam ao longo de dias, como num canal que está crescendo."),
            ("refresh", "{reposicao}", "Quedas dentro do prazo são repostas pelo painel, sem custo."),
        ],
        faq=[
            ("Comprar inscritos no YouTube vale a pena?", "Vale para melhorar a primeira impressão do canal e se aproximar dos 1.000 inscritos do Programa de Parcerias. Não vale se a expectativa é monetizar só com isso: o YouTube também exige horas de exibição e revisa o canal manualmente."),
            ("Comprar inscritos no YouTube dá ban?", "O YouTube remove inscritos que considera spam e pode reduzir esse número com o tempo, por isso a reposição é importante. Entrega gradual e nenhum acesso à sua conta mantêm o risco baixo."),
            ("Os inscritos são brasileiros?", "Não. Este serviço entrega inscritos de perfis internacionais. Preferimos dizer isso claramente a vender uma promessa que não conseguimos cumprir."),
            ("Quanto custam 1.000 inscritos no YouTube?", "Hoje, {preco_mil} por 1.000 inscritos com {reposicao_l}."),
            ("Inscritos comprados ajudam na monetização?", "Contam para o número de inscritos, mas a monetização depende também das horas de exibição e de o canal seguir as políticas do YouTube. Veja a página de horas assistidas para entender essa parte."),
        ],
        related=["comprar-visualizacoes-youtube", "comprar-horas-assistidas-youtube", "comprar-seguidores-tiktok", "comprar-seguidores-instagram", "guia/vale-a-pena-comprar-seguidores", "guia/como-comprar-seguidores"],
    ),
    dict(
        slug="comprar-visualizacoes-instagram", plat="Instagram", icon="ig", quiz=None,
        svc=dict(plat_rx=IG, name_rx=r"visualiza", exclude=r"live|coment|perfil"), unit="visualizações",
        title="Comprar Visualizações Instagram (Reels e Stories)",
        desc="Visualizações para Reels e Stories do Instagram a partir de {preco_min}. Entrega rápida, sem senha e pagamento via PIX.",
        h1="Comprar visualizações no Instagram para Reels e Stories",
        lead="Reels com poucas visualizações parecem não ter dado certo. Dê ao seu vídeo o começo que ele precisa.",
        intro=[
            "No Reels, o contador de visualizações é o primeiro sinal de que um vídeo vale a pena. Um Reels com 200 visualizações é pulado; o mesmo vídeo com 20 mil faz a pessoa parar para entender por que tanta gente assistiu.",
            "As visualizações deste serviço servem para Reels e vídeos públicos. Você manda o link, escolhe a quantidade e acompanha a entrega pelo painel. Para Stories, o pedido vai para o seu @ e alcança os Stories ativos no momento.",
        ],
        why=[
            ("eye", "Contador que chama atenção", "Visualizações altas fazem quem chega assistir até o fim."),
            ("bolt", "Entrega rápida", "O pedido começa em pouco tempo, ideal logo depois de publicar."),
            ("chart", "Pacotes grandes por pouco", "Visualizações são o serviço mais barato por unidade."),
        ],
        faq=[
            ("Serve para Reels e para Stories?", "Serve para os dois, mas o pedido é diferente. Para Reels, você informa o link do vídeo. Para Stories, informa o @ e o pedido alcança os Stories publicados naquele momento."),
            ("Visualizações ajudam no algoritmo?", "Ajudam a primeira impressão de quem chega, e o contador alto aumenta a chance de a pessoa assistir e interagir. O alcance orgânico continua dependendo de retenção e interação reais."),
            ("Quanto custam visualizações no Instagram?", "Hoje, {preco_mil} por 1.000 visualizações. O menor pacote custa {preco_min}."),
            ("O vídeo precisa estar público?", "Sim. Vídeos de perfis privados não recebem visualizações externas."),
        ],
        related=["comprar-curtidas-instagram", "comprar-seguidores-instagram", "comprar-comentarios-instagram", "comprar-visualizacoes-tiktok", "comprar-visualizacoes-youtube", "guia/quanto-custa-1000-seguidores"],
    ),
    dict(
        slug="comprar-visualizacoes-tiktok", plat="TikTok", icon="tt", quiz=None,
        svc=dict(plat_rx=r"tik ?tok", name_rx=r"visualiza", exclude=r"live"), unit="visualizações",
        title="Comprar Visualizações TikTok Barato | a partir de {preco_min}",
        desc="Visualizações para vídeos do TikTok a partir de {preco_min}. Entrega rápida, sem senha e pagamento via PIX.",
        h1="Comprar visualizações no TikTok",
        lead="Dê aos seus vídeos o volume inicial que faz outras pessoas pararem para assistir.",
        intro=[
            "No TikTok, as visualizações aparecem na grade do seu perfil, embaixo de cada vídeo. Uma grade com números altos faz quem visita o perfil maratonar os vídeos; uma grade com números baixos faz a pessoa sair.",
            "Este serviço entrega visualizações em vídeos públicos a partir de um link. O pacote começa em {preco_min}, e dá para distribuir pedidos entre vários vídeos para equilibrar a grade.",
        ],
        why=[
            ("eye", "Grade de perfil mais forte", "Números altos embaixo dos vídeos seguram quem visita o perfil."),
            ("bolt", "Começa em pouco tempo", "Bom para o período logo depois de postar."),
            ("chart", "Custo baixo por mil", "Visualizações custam centavos por mil em pacotes grandes."),
        ],
        faq=[
            ("Visualizações compradas fazem o vídeo viralizar?", "Sozinhas, não. Elas melhoram a primeira impressão; quem decide se o vídeo vai para mais gente é a retenção (quanto do vídeo as pessoas assistem) e a interação."),
            ("Posso dividir as visualizações entre vídeos?", "Pode. Cada pedido vai para um link. Faça um pedido por vídeo com a quantidade que quiser, respeitando o mínimo do pacote."),
            ("Quanto custam 1.000 visualizações no TikTok?", "Hoje, {preco_mil} por 1.000 visualizações. O menor pacote custa {preco_min}."),
        ],
        related=["comprar-seguidores-tiktok", "comprar-curtidas-tiktok", "comprar-visualizacoes-instagram", "comprar-visualizacoes-kwai", "comprar-seguidores-baratos", "guia/como-comprar-seguidores"],
    ),
    dict(
        slug="comprar-visualizacoes-youtube", plat="YouTube", icon="yt", quiz=None,
        svc=dict(plat_rx=r"youtube", name_rx=r"visualiza", exclude=r"live|shorts|an[úu]ncio|ads", prefer_br=False), unit="visualizações",
        title="Comprar Visualizações YouTube | a partir de {preco_min}",
        desc="Visualizações para vídeos do YouTube a partir de {preco_min}, sem senha e com pagamento via PIX. Entenda a diferença entre visualizações e horas assistidas.",
        h1="Comprar visualizações no YouTube",
        lead="Mais visualizações no contador do vídeo, sem acesso à sua conta. Veja também quando faz mais sentido comprar horas assistidas.",
        intro=[
            "O contador de visualizações aparece em todo lugar onde o vídeo é sugerido: busca, página inicial, vídeos relacionados. Um número alto aumenta a chance de clique, principalmente em buscas com vários vídeos parecidos.",
            "Visualizações e horas assistidas são coisas diferentes para o YouTube. Visualizações melhoram o contador; para o Programa de Parcerias, o que conta são as horas de exibição. Se o objetivo é monetizar, veja a página de horas assistidas.",
        ],
        why=[
            ("eye", "Mais cliques na busca", "Entre vídeos parecidos, o com mais visualizações costuma ganhar o clique."),
            ("plant", "Entrega gradual", "As visualizações chegam aos poucos, sem picos estranhos nas estatísticas."),
            ("target", "Um vídeo por pedido", "Você escolhe exatamente qual vídeo recebe o pedido."),
        ],
        faq=[
            ("Comprar visualizações no YouTube vale a pena?", "Vale para dar credibilidade a um vídeo novo ou importante. Não substitui retenção: se as pessoas saem nos primeiros segundos, o YouTube para de recomendar o vídeo."),
            ("Visualizações contam como horas assistidas?", "Não necessariamente. Horas de exibição dependem de quanto tempo cada visualização dura. Para a meta de monetização, existe um serviço específico de horas assistidas."),
            ("Quanto custam 1.000 visualizações no YouTube?", "Hoje, {preco_mil} por 1.000 visualizações. O menor pacote custa {preco_min}."),
        ],
        related=["comprar-inscritos-youtube", "comprar-horas-assistidas-youtube", "comprar-visualizacoes-tiktok", "comprar-visualizacoes-instagram", "guia/vale-a-pena-comprar-seguidores", "guia/quanto-custa-1000-seguidores"],
    ),
    dict(
        slug="comprar-seguidores-kwai", plat="Kwai", icon="kwai", quiz="Kwai",
        svc=dict(fixed=2842), unit="seguidores",
        title="Comprar Seguidores Kwai Brasileiros | a partir de {preco_min}",
        desc="Seguidores brasileiros no Kwai a partir de {preco_min}, com {reposicao_l}, sem senha e pagamento via PIX.",
        h1="Comprar seguidores no Kwai, brasileiros e baratos",
        lead="O Kwai é uma das redes de vídeo mais brasileiras que existem. Seguidores daqui combinam com o público de lá.",
        intro=[
            "O Kwai cresceu no Brasil com um público próprio, forte fora dos grandes centros e muito engajado com humor, música e dia a dia. Por isso, seguidores brasileiros fazem ainda mais diferença aqui do que em outras redes.",
            "Este é também o serviço de seguidores com o melhor custo do catálogo: 1.000 seguidores {origem_l} saem por {preco_mil}, com {reposicao_l} e entrega rápida.",
        ],
        why=[
            ("users", "Seguidores {origem_l}", "Combinam com o público que já usa o Kwai todos os dias."),
            ("chart", "Menor preço por mil", "O Kwai tem o melhor custo por seguidor de todas as plataformas."),
            ("refresh", "{reposicao}", "Quedas dentro do prazo são repostas pelo painel."),
        ],
        faq=[
            ("Comprar seguidores no Kwai é seguro?", "É, com entrega gradual e sem pedido de senha. A gente usa só o link ou o @ do seu perfil público."),
            ("Por que seguidores no Kwai são mais baratos?", "O custo de cada serviço varia com a oferta de perfis em cada rede. No Kwai, essa oferta é maior, e a gente repassa a diferença no preço."),
            ("Quanto custam 1.000 seguidores no Kwai?", "Hoje, {preco_mil} por 1.000 seguidores {origem_l} com {reposicao_l}."),
        ],
        related=["comprar-visualizacoes-kwai", "comprar-seguidores-tiktok", "comprar-seguidores-instagram", "comprar-seguidores-baratos", "comprar-seguidores-brasileiros", "guia/quanto-custa-1000-seguidores"],
    ),
    dict(
        slug="comprar-seguidores-twitter", plat="Twitter/X", icon="users", quiz=None,
        svc=dict(plat_rx=r"twitter", name_rx=r"seguidor"), unit="seguidores",
        title="Comprar Seguidores Twitter (X) | a partir de {preco_min}",
        desc="Seguidores para o Twitter/X a partir de {preco_min}, com {reposicao_l}, sem senha e pagamento via PIX.",
        h1="Comprar seguidores no Twitter (X)",
        lead="Mais seguidores no seu perfil do X, entregues sem acesso à sua conta.",
        intro=[
            "No X, o número de seguidores aparece em cada resposta que você dá e em cada vez que alguém passa o mouse no seu nome. Perfis com mais seguidores têm as respostas levadas mais a sério e aparecem mais em discussões.",
            "Os seguidores deste serviço são {origem_l}: o X não tem, hoje, uma oferta de perfis brasileiros com a qualidade que a gente exige. Eles chegam aos poucos e contam com {reposicao_l}.",
        ],
        why=[
            ("users", "Autoridade nas conversas", "Mais seguidores dão peso às suas respostas e posts."),
            ("plant", "Entrega gradual", "Os seguidores entram aos poucos, como num perfil em alta."),
            ("refresh", "{reposicao}", "Quedas dentro do prazo são repostas pelo painel."),
        ],
        faq=[
            ("Os seguidores do Twitter são brasileiros?", "Não. Este serviço entrega seguidores {origem_l}. Se o seu objetivo é interação em português, combine com conteúdo e respostas em conversas brasileiras."),
            ("Preciso informar senha?", "Nunca. Basta o @ do perfil público."),
            ("Quanto custam 1.000 seguidores no Twitter?", "Hoje, {preco_mil} por 1.000 seguidores com {reposicao_l}."),
        ],
        related=["comprar-seguidores-threads", "comprar-seguidores-instagram", "comprar-seguidores-facebook", "comprar-seguidores-reais", "guia/como-saber-se-seguidores-sao-reais", "servicos"],
    ),
    dict(
        slug="comprar-curtidas-tiktok", plat="TikTok", icon="tt", quiz=None,
        svc=dict(plat_rx=r"tik ?tok", name_rx=r"curtida", exclude=r"coment|live"), unit="curtidas",
        title="Comprar Curtidas TikTok | a partir de {preco_min}",
        desc="Curtidas {origem_l} para vídeos do TikTok a partir de {preco_min}. Entrega rápida, sem senha e pagamento via PIX.",
        h1="Comprar curtidas no TikTok",
        lead="Curtidas dão prova social ao vídeo e fazem quem chega assistir com mais atenção.",
        intro=[
            "Curtidas são o sinal mais visível de que um vídeo agradou. No TikTok, elas aparecem ao lado do vídeo enquanto ele toca e ajudam quem está rolando o feed a decidir se para ou passa.",
            "As curtidas deste serviço são {origem_l} e vão para o vídeo que você escolher, a partir do link. O menor pacote custa {preco_min}.",
        ],
        why=[
            ("heart", "Prova social em cada vídeo", "Um vídeo curtido convence mais do que um vídeo parado."),
            ("bolt", "Entrega rápida", "Bom para os primeiros minutos depois de postar."),
            ("target", "Você escolhe o vídeo", "Cada pedido vai para um link específico."),
        ],
        faq=[
            ("Comprar curtidas no TikTok é seguro?", "É. Curtidas são a interação mais comum da plataforma, e nenhum acesso à sua conta é necessário."),
            ("Quanto custam 1.000 curtidas no TikTok?", "Hoje, {preco_mil} por 1.000 curtidas. O menor pacote custa {preco_min}."),
            ("As curtidas somem?", "Parte pode cair com limpezas periódicas do TikTok. {reposicao} neste serviço."),
        ],
        related=["comprar-seguidores-tiktok", "comprar-visualizacoes-tiktok", "comprar-curtidas-instagram", "comprar-curtidas-facebook", "comprar-seguidores-baratos", "servicos"],
    ),
    dict(
        slug="comprar-seguidores-facebook", plat="Facebook", icon="users", quiz=None,
        svc=dict(plat_rx=r"facebook", name_rx=r"seguidor"), unit="seguidores",
        title="Comprar Seguidores Facebook | a partir de {preco_min}",
        desc="Seguidores para páginas e perfis do Facebook a partir de {preco_min}, sem senha e com pagamento via PIX.",
        h1="Comprar seguidores no Facebook para página e perfil",
        lead="Mais seguidores na sua página ou perfil do Facebook, sem precisar de acesso à conta.",
        intro=[
            "No Facebook, o número de seguidores da página é um dos primeiros dados que um cliente vê antes de mandar mensagem ou comprar. Para negócios locais, uma página com poucos seguidores parece abandonada, mesmo quando a empresa está funcionando.",
            "Os seguidores deste serviço são {origem_l} e servem tanto para páginas quanto para perfis profissionais. {reposicao}.",
        ],
        why=[
            ("store", "Página com cara de empresa ativa", "Mais seguidores passam confiança para quem pesquisa o seu negócio."),
            ("users", "Serve para página e perfil", "Basta o link público da página ou do perfil."),
            ("chart", "Preço baixo por mil", "Um dos serviços de seguidores mais baratos do catálogo."),
        ],
        faq=[
            ("Os seguidores do Facebook são brasileiros?", "Não. Este serviço entrega seguidores {origem_l}. Para anúncios locais, combine com campanhas segmentadas por região."),
            ("Serve para página de empresa?", "Serve. Informe o link público da página. Para perfis pessoais, o modo profissional precisa permitir seguidores."),
            ("Quanto custam 1.000 seguidores no Facebook?", "Hoje, {preco_mil} por 1.000 seguidores."),
        ],
        related=["comprar-curtidas-facebook", "comprar-seguidores-instagram", "comprar-seguidores-twitter", "comprar-seguidores-baratos", "servicos", "guia/como-comprar-seguidores"],
    ),
    dict(
        slug="comprar-curtidas-facebook", plat="Facebook", icon="users", quiz=None,
        svc=dict(plat_rx=r"facebook", name_rx=r"curtida", exclude=r"coment"), unit="curtidas",
        title="Comprar Curtidas Facebook | a partir de {preco_min}",
        desc="Curtidas para posts e páginas do Facebook a partir de {preco_min}, sem senha e com pagamento via PIX.",
        h1="Comprar curtidas no Facebook",
        lead="Curtidas nos seus posts e na sua página, sem acesso à sua conta.",
        intro=[
            "Um post com curtidas é lido como um post que deu certo. No Facebook, isso vale em dobro para páginas de negócio: é o que o cliente vê quando procura a empresa antes de entrar em contato.",
            "As curtidas deste serviço são {origem_l} e vão para o post que você escolher, a partir do link. O menor pacote custa {preco_min}.",
        ],
        why=[
            ("heart", "Posts com cara de sucesso", "Mais curtidas convencem quem chega depois."),
            ("target", "Um post por pedido", "Você escolhe exatamente onde as curtidas entram."),
            ("chart", "Pacotes a partir de {preco_min}", "Bom para testar antes de pedidos maiores."),
        ],
        faq=[
            ("Posso escolher o post?", "Pode. Cada pedido vai para o link de um post público."),
            ("Quanto custam 1.000 curtidas no Facebook?", "Hoje, {preco_mil} por 1.000 curtidas."),
            ("Preciso informar senha?", "Nunca. Basta o link público do post."),
        ],
        related=["comprar-seguidores-facebook", "comprar-curtidas-instagram", "comprar-curtidas-tiktok", "servicos", "comprar-seguidores-baratos", "guia/como-comprar-seguidores"],
    ),
    dict(
        slug="comprar-comentarios-instagram", plat="Instagram", icon="ig", quiz=None,
        svc=dict(plat_rx=IG, name_rx=r"coment"), unit="comentários",
        title="Comprar Comentários Instagram | a partir de {preco_min}",
        desc="Comentários {origem_l} para posts e Reels do Instagram a partir de {preco_min}. Sem senha e com pagamento via PIX.",
        h1="Comprar comentários no Instagram",
        lead="Comentários em português deixam o post com cara de conversa, não de vitrine vazia.",
        intro=[
            "Comentários são a interação que mais pesa para o Instagram e a que mais convence quem chega: um post com conversa embaixo parece vivo. Para lojas, eles ainda respondem dúvidas que outros clientes teriam.",
            "Os comentários deste serviço são {origem_l} e vão para o post que você escolher. Em alguns pacotes, você mesmo escreve os comentários.",
        ],
        why=[
            ("heart", "A interação que mais pesa", "Comentários valem mais para o algoritmo do que curtidas."),
            ("users", "Comentários {origem_l}", "Texto em português, coerente com o seu conteúdo."),
            ("target", "Você escolhe o post", "Cada pedido vai para um link específico."),
        ],
        faq=[
            ("Posso escrever os comentários?", "Nos pacotes personalizados, sim: você envia a lista de comentários, um por linha. Nos pacotes comuns, os comentários são variados e positivos."),
            ("Quanto custam comentários no Instagram?", "O menor pacote custa {preco_min}. O valor por 1.000 comentários fica em {preco_mil}."),
            ("Comentários comprados parecem falsos?", "Comentários genéricos demais parecem. Por isso vale escrever comentários que combinem com o post ou pedir pacotes brasileiros."),
        ],
        related=["comprar-curtidas-instagram", "comprar-seguidores-instagram", "comprar-visualizacoes-instagram", "comprar-seguidores-brasileiros", "guia/como-saber-se-seguidores-sao-reais", "servicos"],
    ),
    dict(
        slug="comprar-horas-assistidas-youtube", plat="YouTube", icon="yt", quiz=None,
        svc=dict(plat_rx=r"youtube", name_rx=r"watch ?time|horas de exibi"), unit="horas", no_packages=True,
        title="Comprar Horas Assistidas YouTube para Monetização: o que Funciona",
        desc="Entenda como funcionam as horas assistidas do YouTube, o que conta para a monetização (4.000 horas e 1.000 inscritos) e quais são os riscos antes de comprar.",
        h1="Horas assistidas no YouTube: o que conta para a monetização",
        lead="Antes de comprar horas de exibição, entenda a regra do Programa de Parcerias e por que ninguém pode garantir a aprovação do seu canal.",
        note="Nenhum serviço pode garantir a monetização: o YouTube revisa cada canal manualmente e pode recusar canais com exibição artificial. Use horas assistidas como complemento de conteúdo real, nunca como substituto.",
        intro=[
            "Para entrar no Programa de Parcerias do YouTube, o canal precisa de 1.000 inscritos e de 4.000 horas de exibição públicas nos últimos 12 meses (ou 10 milhões de visualizações válidas em Shorts nos últimos 90 dias). Depois disso, o canal passa por uma revisão manual.",
            "Horas assistidas são vendidas como visualizações longas em vídeos públicos, geralmente de 30 minutos ou mais. Elas somam ao contador de horas, mas o YouTube pode desconsiderar exibições que considere artificiais, e a revisão do canal olha também para o conteúdo e a origem do tráfego.",
        ],
        why=[
            ("clock", "Entenda a regra antes", "1.000 inscritos + 4.000 horas em 12 meses, ou 10 milhões de views em Shorts."),
            ("shield", "Sem acesso à conta", "Os pedidos usam só o link público do vídeo."),
            ("info", "Sem promessa de aprovação", "Quem garante monetização está prometendo algo que não controla."),
        ],
        faq=[
            ("Comprar horas assistidas garante a monetização?", "Não. As horas somam ao contador, mas a aprovação depende de uma revisão manual do YouTube, que pode recusar canais com exibição artificial."),
            ("Quantas horas preciso para monetizar?", "4.000 horas de exibição públicas nos últimos 12 meses, junto com 1.000 inscritos. A alternativa para Shorts é 10 milhões de visualizações válidas em 90 dias."),
            ("Qual vídeo deve receber as horas?", "Vídeos longos e públicos, com mais de 30 minutos. Vídeos curtos, privados ou não listados não contam para as horas de exibição públicas."),
            ("Como faço o pedido?", "Pelo painel, escolhendo o serviço de horas assistidas e informando o link do vídeo. O preço aparece antes do pagamento."),
        ],
        related=["comprar-inscritos-youtube", "comprar-visualizacoes-youtube", "guia/vale-a-pena-comprar-seguidores", "guia/como-escolher-site-para-comprar-seguidores", "servicos", "comprar-seguidores-tiktok"],
    ),
    dict(
        slug="comprar-seguidores-twitch", plat="Twitch", icon="users", quiz=None,
        svc=dict(plat_rx=r"twitch", name_rx=r"seguidor"), unit="seguidores",
        title="Comprar Seguidores Twitch | a partir de {preco_min}",
        desc="Seguidores para o seu canal da Twitch a partir de {preco_min}, sem senha e com pagamento via PIX.",
        h1="Comprar seguidores na Twitch",
        lead="Mais seguidores no seu canal, sem acesso à conta. Veja o que eles ajudam no caminho para Afiliado.",
        intro=[
            "Na Twitch, o número de seguidores aparece no canal e na tela de quem está decidindo em qual live entrar. Um canal pequeno perde espectadores para canais com números maiores, mesmo com a mesma qualidade de conteúdo.",
            "Os seguidores deste serviço são {origem_l}. O programa de Afiliado da Twitch pede, entre outros critérios, 50 seguidores, e também tempo de transmissão, dias transmitidos e média de espectadores, que seguidores sozinhos não resolvem.",
        ],
        why=[
            ("users", "Canal com cara de canal", "Seguidores ajudam quem chega a ficar na live."),
            ("bolt", "Entrega rápida", "Os seguidores começam a entrar pouco depois do pedido."),
            ("shield", "Sem acesso à conta", "Só o nome do canal é necessário."),
        ],
        faq=[
            ("Os seguidores da Twitch são brasileiros?", "Não. Este serviço entrega seguidores {origem_l}."),
            ("Seguidores ajudam a virar Afiliado?", "Ajudam no critério de seguidores (50). Os outros critérios, como horas transmitidas e média de espectadores, continuam dependendo das suas lives."),
            ("Quanto custam 1.000 seguidores na Twitch?", "Hoje, {preco_mil} por 1.000 seguidores."),
        ],
        related=["comprar-seguidores-kick", "comprar-inscritos-youtube", "comprar-membros-discord", "servicos", "comprar-seguidores-baratos", "guia/como-comprar-seguidores"],
    ),
    dict(
        slug="comprar-seguidores-kick", plat="Kick", icon="users", quiz=None,
        svc=dict(plat_rx=r"\bkick\b", name_rx=r"seguidor"), unit="seguidores",
        title="Comprar Seguidores Kick | a partir de {preco_min}",
        desc="Seguidores para o seu canal na Kick a partir de {preco_min}, com {reposicao_l}, sem senha e pagamento via PIX.",
        h1="Comprar seguidores na Kick",
        lead="Mais seguidores no seu canal da Kick, sem acesso à conta.",
        intro=[
            "A Kick cresceu rápido entre streamers brasileiros, e o número de seguidores é um dos primeiros filtros de quem procura uma live nova para assistir.",
            "Os seguidores deste serviço são {origem_l}, com {reposicao_l}. Você informa só o nome do canal.",
        ],
        why=[
            ("users", "Mais peso na descoberta", "Canais com mais seguidores chamam mais a atenção de quem navega pela plataforma."),
            ("refresh", "{reposicao}", "Quedas dentro do prazo são repostas pelo painel."),
            ("shield", "Sem acesso à conta", "Só o nome do canal é necessário."),
        ],
        faq=[
            ("Os seguidores da Kick são brasileiros?", "Não. Este serviço entrega seguidores {origem_l}."),
            ("Preciso informar senha?", "Nunca. Basta o nome público do canal."),
            ("Quanto custam 1.000 seguidores na Kick?", "Hoje, {preco_mil} por 1.000 seguidores com {reposicao_l}."),
        ],
        related=["comprar-seguidores-twitch", "comprar-membros-discord", "comprar-inscritos-youtube", "servicos", "comprar-seguidores-baratos", "guia/como-comprar-seguidores"],
    ),
    dict(
        slug="comprar-membros-telegram", plat="Telegram", icon="users", quiz=None,
        svc=dict(plat_rx=r"telegram", name_rx=r"membro", prefer_br=False), unit="membros",
        title="Comprar Membros Telegram | a partir de {preco_min}",
        desc="Membros para canais e grupos do Telegram a partir de {preco_min}. Sem acesso ao administrador e com pagamento via PIX.",
        h1="Comprar membros no Telegram para canal e grupo",
        lead="Canais com mais membros convencem quem chega pelo link de convite. Sem acesso ao administrador.",
        intro=[
            "No Telegram, o número de membros aparece logo no topo do canal ou grupo, antes da primeira mensagem. É o que faz alguém que recebeu o link de convite decidir se entra ou não.",
            "Os membros deste serviço são {origem_l} e entram pelo link público do canal ou grupo. {reposicao}.",
        ],
        why=[
            ("users", "Mais entradas pelo convite", "Um número alto de membros faz quem recebe o link entrar."),
            ("shield", "Sem acesso de administrador", "Basta o link público do canal ou grupo."),
            ("chart", "Pacotes grandes por pouco", "Membros de Telegram estão entre os serviços mais baratos."),
        ],
        faq=[
            ("Serve para canal e para grupo?", "Serve para os dois, desde que o link seja público."),
            ("Os membros são brasileiros?", "Este serviço entrega membros {origem_l}. Existem opções brasileiras no painel, com preço diferente."),
            ("Quanto custam 1.000 membros no Telegram?", "Hoje, {preco_mil} por 1.000 membros."),
        ],
        related=["comprar-membros-discord", "comprar-seguidores-instagram", "servicos", "comprar-seguidores-baratos", "guia/como-escolher-site-para-comprar-seguidores", "comprar-seguidores-twitter"],
    ),
    dict(
        slug="comprar-membros-discord", plat="Discord", icon="users", quiz=None,
        svc=dict(plat_rx=r"discord", name_rx=r"membro"), unit="membros",
        title="Comprar Membros Discord | a partir de {preco_min}",
        desc="Membros para o seu servidor do Discord a partir de {preco_min}, com {reposicao_l} e pagamento via PIX.",
        h1="Comprar membros no Discord",
        lead="Servidores com mais membros recebem mais pessoas pelo convite. Sem acesso de administrador.",
        intro=[
            "No Discord, o convite para um servidor mostra quantos membros ele tem e quantos estão online. Um servidor pequeno parece vazio, e quem recebe o convite desiste antes de entrar.",
            "Os membros deste serviço são {origem_l}, com {reposicao_l}, e entram pelo link de convite do servidor.",
        ],
        why=[
            ("users", "Convites que convertem", "Mais membros no convite fazem mais gente entrar."),
            ("refresh", "{reposicao}", "Quedas dentro do prazo são repostas pelo painel."),
            ("shield", "Sem acesso de administrador", "Basta um link de convite sem data de expiração."),
        ],
        faq=[
            ("Que link preciso enviar?", "Um link de convite do servidor sem data de expiração e sem limite de usos."),
            ("Os membros são brasileiros?", "Este serviço entrega membros {origem_l}."),
            ("Quanto custam 1.000 membros no Discord?", "Hoje, {preco_mil} por 1.000 membros com {reposicao_l}."),
        ],
        related=["comprar-membros-telegram", "comprar-seguidores-twitch", "comprar-seguidores-kick", "servicos", "guia/como-comprar-seguidores", "comprar-seguidores-baratos"],
    ),
    dict(
        slug="comprar-ouvintes-spotify", plat="Spotify", icon="users", quiz=None,
        svc=dict(plat_rx=r"spotify", name_rx=r"plays|ouvinte|stream"), unit="plays",
        title="Comprar Plays e Ouvintes Spotify | a partir de {preco_min}",
        desc="Plays para músicas e ouvintes no Spotify a partir de {preco_min}. Sem acesso à sua conta de artista e com pagamento via PIX.",
        h1="Comprar plays e ouvintes no Spotify",
        lead="Mais reproduções nas suas faixas, sem acesso à sua conta de artista.",
        intro=[
            "No Spotify, o contador de reproduções aparece ao lado de cada faixa no perfil do artista. Faixas com poucos plays passam a impressão de lançamento que não pegou, o que afasta ouvintes novos e curadores de playlist.",
            "Os plays deste serviço vão para a faixa que você indicar, a partir do link. O menor pacote custa {preco_min}.",
        ],
        why=[
            ("chart", "Faixas com cara de lançamento forte", "Contadores altos chamam atenção de novos ouvintes."),
            ("shield", "Sem acesso à conta de artista", "Basta o link público da faixa."),
            ("bolt", "Entrega rápida", "Bom para a semana de lançamento."),
        ],
        faq=[
            ("Preciso de acesso ao Spotify for Artists?", "Não. Basta o link público da música."),
            ("Plays comprados geram royalties?", "Não conte com isso. O Spotify filtra reproduções que considera artificiais, e o objetivo aqui é a prova social do contador, não a receita."),
            ("Quanto custam 1.000 plays no Spotify?", "Hoje, {preco_mil} por 1.000 plays."),
        ],
        related=["comprar-inscritos-youtube", "comprar-visualizacoes-youtube", "comprar-seguidores-instagram", "servicos", "comprar-seguidores-baratos", "guia/vale-a-pena-comprar-seguidores"],
    ),
    dict(
        slug="comprar-visualizacoes-kwai", plat="Kwai", icon="kwai", quiz=None,
        svc=dict(plat_rx=r"kwai", name_rx=r"visualiza", exclude=r"live"), unit="visualizações",
        title="Comprar Visualizações Kwai | a partir de {preco_min}",
        desc="Visualizações {origem_l} para vídeos do Kwai a partir de {preco_min}. Sem senha e com pagamento via PIX.",
        h1="Comprar visualizações no Kwai",
        lead="Vídeos com mais visualizações fazem quem chega ao seu perfil assistir mais.",
        intro=[
            "No Kwai, as visualizações aparecem na grade do perfil e embaixo de cada vídeo. Uma grade forte faz quem visita o perfil assistir um vídeo atrás do outro.",
            "As visualizações deste serviço são {origem_l} e vão para o vídeo que você indicar. O menor pacote custa {preco_min}.",
        ],
        why=[
            ("eye", "Grade de perfil mais forte", "Números altos seguram quem visita o perfil."),
            ("users", "Visualizações {origem_l}", "Combinam com o público do Kwai."),
            ("chart", "Custo baixo por mil", "Pacotes grandes por pouco."),
        ],
        faq=[
            ("Visualizações fazem o vídeo viralizar?", "Sozinhas, não. Elas melhoram a primeira impressão; o alcance continua dependendo de quanto do vídeo as pessoas assistem."),
            ("Quanto custam 1.000 visualizações no Kwai?", "Hoje, {preco_mil} por 1.000 visualizações."),
            ("Preciso informar senha?", "Nunca. Basta o link público do vídeo."),
        ],
        related=["comprar-seguidores-kwai", "comprar-visualizacoes-tiktok", "comprar-visualizacoes-instagram", "comprar-seguidores-baratos", "servicos", "guia/como-comprar-seguidores"],
    ),
    dict(
        slug="comprar-seguidores-threads", plat="Threads", icon="users", quiz=None,
        svc=dict(plat_rx=r"threads", name_rx=r"seguidor"), unit="seguidores",
        title="Comprar Seguidores Threads | a partir de {preco_min}",
        desc="Seguidores para o seu perfil do Threads a partir de {preco_min}, com {reposicao_l}, sem senha e pagamento via PIX.",
        h1="Comprar seguidores no Threads",
        lead="Mais seguidores no Threads, sem acesso à sua conta do Instagram.",
        intro=[
            "O Threads puxa o seu perfil do Instagram, mas os seguidores são contados à parte. Quem entra na rede agora tem a chance de crescer antes que ela fique concorrida.",
            "Os seguidores deste serviço são {origem_l}, com {reposicao_l}. Você informa só o @.",
        ],
        why=[
            ("users", "Cresça cedo numa rede nova", "Perfis que crescem cedo ganham espaço nas conversas."),
            ("refresh", "{reposicao}", "Quedas dentro do prazo são repostas pelo painel."),
            ("shield", "Sem acesso à conta", "Só o @ público é necessário."),
        ],
        faq=[
            ("Os seguidores do Threads são brasileiros?", "Não. Este serviço entrega seguidores {origem_l}."),
            ("Os seguidores do Threads contam no Instagram?", "Não. As duas redes contam seguidores separadamente."),
            ("Quanto custam 1.000 seguidores no Threads?", "Hoje, {preco_mil} por 1.000 seguidores com {reposicao_l}."),
        ],
        related=["comprar-seguidores-instagram", "comprar-seguidores-twitter", "comprar-curtidas-instagram", "servicos", "comprar-seguidores-reais", "guia/como-comprar-seguidores"],
    ),
]

# ----------------------------------------------------------------------------- conteúdo: intenção

INTENT = [
    dict(
        slug="comprar-seguidores-brasileiros", icon="users",
        title="Comprar Seguidores Brasileiros: Instagram, TikTok e Kwai",
        desc="Onde comprar seguidores brasileiros de verdade: preços por plataforma, com reposição, sem senha e pagamento via PIX. Compare Instagram, TikTok e Kwai.",
        h1="Comprar seguidores brasileiros",
        lead="Seguidores do Brasil interagem com conteúdo em português. Veja em quais plataformas a gente entrega perfis brasileiros e quanto custa cada uma.",
        kind="br",
        body=[
            ("Por que seguidores brasileiros valem mais", [
                "Seguidores internacionais custam menos, mas raramente interagem com um post em português. Um perfil com 10 mil seguidores e quase nenhuma curtida chama mais atenção negativa do que um perfil menor e ativo.",
                "Seguidores brasileiros combinam com o idioma, os horários e as referências do seu conteúdo. Eles também deixam o perfil coerente para quem olha de fora, seja um cliente, seja uma marca procurando criadores.",
            ]),
            ("Onde temos seguidores brasileiros", [
                "Hoje, entregamos seguidores brasileiros com reposição no Instagram, no TikTok e no Kwai. No YouTube, no Twitter/X, no Facebook, na Twitch e no Threads, os serviços disponíveis são internacionais, e a gente avisa isso em cada página.",
            ]),
        ],
        faq=[
            ("Como saber se os seguidores são brasileiros?", "Abra alguns perfis que chegaram: nome, foto, bio e publicações em português, seguindo contas brasileiras. Perfis sem foto e com nomes estrangeiros em série são sinal de serviço internacional."),
            ("Seguidores brasileiros custam mais?", "Custam, porque a oferta de perfis brasileiros é menor. No Instagram, a diferença é de duas a cinco vezes em relação aos internacionais."),
            ("Posso escolher homens ou mulheres?", "No Instagram, sim: há serviços separados para seguidoras e seguidores brasileiros."),
        ],
        related=["comprar-seguidores-instagram", "comprar-seguidores-tiktok", "comprar-seguidores-kwai", "comprar-seguidores-reais", "guia/como-saber-se-seguidores-sao-reais", "guia/quanto-custa-1000-seguidores"],
    ),
    dict(
        slug="comprar-seguidores-reais", icon="check-circle",
        title="Comprar Seguidores Reais: Como Identificar e Onde Comprar | {ano}",
        desc="O que são seguidores reais, como diferenciar de robôs e onde comprar seguidores reais e brasileiros com reposição, sem senha e via PIX.",
        h1="Comprar seguidores reais",
        lead="Todo site diz que vende seguidores reais. Veja o que isso significa na prática e como conferir antes e depois da compra.",
        kind="br",
        body=[
            ("O que é um seguidor real", [
                "Na prática, “real” quer dizer um perfil com cara de pessoa: foto, nome, publicações e seguindo outras contas. Não quer dizer um fã do seu conteúdo. Nenhum serviço de seguidores entrega pessoas que decidiram te seguir por conta própria, e quem promete isso está exagerando.",
                "O que muda entre um serviço bom e um ruim é a qualidade desses perfis e o quanto eles ficam. Perfis vazios somem nas limpezas das plataformas; perfis bem construídos ficam, e a reposição cobre o que cair.",
            ]),
            ("Como a gente classifica a qualidade", [
                "Cada serviço do nosso catálogo tem a origem (brasileiros ou internacionais), o nível de qualidade e o prazo de reposição descritos antes da compra. Nas páginas de cada plataforma, você vê exatamente o que está comprando.",
            ]),
        ],
        faq=[
            ("Seguidores reais interagem?", "Alguns, principalmente quando são do mesmo nicho e do mesmo país. Mas conte com eles para prova social, não para comentários constantes."),
            ("Como identificar seguidores falsos?", "Perfis sem foto, com nomes aleatórios, sem publicações e seguindo milhares de contas. O guia de como saber se os seguidores são reais tem um passo a passo."),
            ("Seguidores reais somem?", "Podem cair aos poucos quando a plataforma faz limpezas. Por isso vale escolher serviços com reposição."),
        ],
        related=["comprar-seguidores-brasileiros", "comprar-seguidores-instagram", "comprar-seguidores-tiktok", "guia/como-saber-se-seguidores-sao-reais", "guia/vale-a-pena-comprar-seguidores", "comprar-curtidas-instagram"],
    ),
    dict(
        slug="comprar-seguidores-baratos", icon="chart",
        title="Comprar Seguidores Baratos: Preços por Plataforma em {ano}",
        desc="Tabela com os menores preços para comprar seguidores no Instagram, TikTok, Kwai, YouTube e outras redes, com PIX. Veja o que muda entre o barato e o bom.",
        h1="Comprar seguidores baratos",
        lead="Os menores preços do nosso catálogo, por plataforma, e o que você ganha ou perde quando escolhe o mais barato.",
        kind="cheap",
        body=[
            ("O que faz um seguidor ser barato", [
                "O preço depende de três coisas: a origem dos perfis (internacionais custam menos), a qualidade (perfis mais completos custam mais) e a reposição (serviços que repõem quedas custam mais). A tabela abaixo mostra o menor preço de cada plataforma já com essas diferenças.",
                "Ofertas de “seguidores por 1 real” costumam ser pacotes de 10 a 50 seguidores internacionais, sem reposição. Servem para testar o site, não para mudar o perfil.",
            ]),
        ],
        faq=[
            ("Qual a rede com seguidores mais baratos?", "No nosso catálogo, o Kwai tem o menor preço por seguidor brasileiro."),
            ("Seguidores baratos dão ban?", "O preço não causa ban; o que aumenta o risco é a entrega muito rápida e perfis de baixa qualidade. Prefira entrega gradual."),
            ("Existe seguidor por 1 real?", "Existe pacote pequeno por esse valor em alguns sites. Aqui, o pedido mínimo é de R$ 4,90, para cobrir a entrega com reposição."),
        ],
        related=["comprar-seguidores-kwai", "comprar-seguidores-instagram", "comprar-seguidores-tiktok", "guia/quanto-custa-1000-seguidores", "comprar-seguidores-brasileiros", "servicos"],
    ),
]

# ----------------------------------------------------------------------------- conteúdo: guias
# body = lista de (título H2, [parágrafos ou ('ul', [itens]) ou ('table', ...)])

GUIDES = [
    dict(
        slug="vale-a-pena-comprar-seguidores",
        title="Vale a Pena Comprar Seguidores? É Seguro, Dá Ban ou É Crime?",
        desc="Respostas diretas: comprar seguidores é crime? Dá ban? Vale a pena? Veja quando faz sentido, quando não faz e como reduzir os riscos.",
        h1="Vale a pena comprar seguidores em {ano}?",
        lead="Respostas diretas para as três dúvidas mais buscadas: se é crime, se dá ban e se vale o dinheiro.",
        body=[
            ("Comprar seguidores é crime?", [
                "Não. Não existe lei no Brasil que proíba comprar seguidores para o seu próprio perfil. O que existe são os termos de uso das plataformas, que proíbem atividade inautêntica. O risco, portanto, é de a plataforma remover seguidores ou limitar o alcance, não de um problema legal.",
                "A exceção é usar números inflados para enganar consumidores em publicidade, como um influenciador que apresenta métricas falsas para fechar um contrato. Aí a questão deixa de ser o seguidor e passa a ser propaganda enganosa.",
            ]),
            ("Comprar seguidores dá ban?", [
                "Banimento por comprar seguidores é raro. O que acontece com mais frequência é a plataforma remover parte dos seguidores numa limpeza ou reduzir o alcance de perfis com comportamento artificial.",
                ("ul", [
                    "<strong>Aumenta o risco:</strong> entregar a senha, receber milhares de seguidores em minutos, perfis sem foto e de países aleatórios.",
                    "<strong>Reduz o risco:</strong> entrega gradual, perfis do mesmo país e do mesmo nicho, e nenhum acesso à sua conta.",
                ]),
            ]),
            ("Quando vale a pena", [
                ("ul", [
                    "Quando o perfil é novo e o conteúdo é bom, mas o número baixo afasta quem chega.",
                    "Quando falta pouco para um requisito da plataforma, como lives no TikTok ou os 1.000 inscritos do YouTube.",
                    "Quando o perfil é de uma loja e o número de seguidores influencia a confiança de quem vai comprar.",
                ]),
            ]),
            ("Quando não vale a pena", [
                ("ul", [
                    "Quando a expectativa é que os seguidores comprados comentem e comprem. Eles são prova social, não clientes.",
                    "Quando o perfil não posta. Um perfil com milhares de seguidores e três publicações chama mais atenção negativa do que um perfil pequeno.",
                    "Quando o objetivo é monetizar o YouTube só com números comprados: a revisão do canal olha muito mais do que isso.",
                ]),
            ]),
        ],
        faq=[
            ("Comprar seguidores é crime no Brasil?", "Não. Nenhuma lei proíbe comprar seguidores para o próprio perfil. As plataformas proíbem nos termos de uso, e o risco é de remoção de seguidores ou perda de alcance."),
            ("O Instagram descobre que comprei seguidores?", "Ele identifica padrões artificiais, como picos repentinos e perfis falsos em massa. Entrega gradual e perfis brasileiros deixam o crescimento parecido com o natural."),
            ("Posso perder minha conta?", "É muito raro, e costuma acontecer quando a pessoa entrega a senha para o serviço. Nunca entregue a sua."),
        ],
        related=["guia/como-saber-se-seguidores-sao-reais", "guia/como-escolher-site-para-comprar-seguidores", "comprar-seguidores-instagram", "comprar-seguidores-tiktok", "comprar-inscritos-youtube", "comprar-seguidores-reais"],
    ),
    dict(
        slug="quanto-custa-1000-seguidores",
        title="Quanto Custa 1.000 Seguidores em {ano}? Tabela por Plataforma",
        desc="Tabela atualizada com quanto custam 1.000 seguidores, curtidas e visualizações no Instagram, TikTok, Kwai, YouTube e outras redes. Entenda o que muda o preço.",
        h1="Quanto custa 1.000 seguidores em {ano}?",
        lead="A tabela abaixo usa os preços reais do nosso catálogo, atualizados em {data}.",
        body=[
            ("Tabela de preços por 1.000", ["__PRICE_TABLE__"]),
            ("O que muda o preço", [
                ("ul", [
                    "<strong>Origem:</strong> perfis brasileiros custam de duas a cinco vezes mais do que internacionais.",
                    "<strong>Qualidade:</strong> perfis com foto, publicações e atividade custam mais e caem menos.",
                    "<strong>Reposição:</strong> serviços que repõem quedas por 30 dias ou mais custam mais.",
                    "<strong>Plataforma:</strong> inscritos no YouTube são o serviço mais caro; visualizações são o mais barato.",
                ]),
            ]),
            ("Por que existe seguidor muito mais barato por aí", [
                "Pacotes muito baratos quase sempre são internacionais, sem reposição e entregues de uma vez. Eles resolvem o número por alguns dias e costumam cair na primeira limpeza da plataforma.",
            ]),
        ],
        faq=[
            ("Quanto custa 1.000 seguidores no Instagram?", "No nosso catálogo, a partir de {ig_mil} para seguidores brasileiros com reposição."),
            ("Qual o seguidor mais barato?", "O Kwai tem o menor preço por seguidor brasileiro, a partir de {kwai_mil} por 1.000."),
            ("Os preços mudam?", "Mudam conforme a oferta de cada serviço. Esta página é atualizada junto com o catálogo."),
        ],
        related=["comprar-seguidores-baratos", "comprar-seguidores-instagram", "comprar-seguidores-tiktok", "comprar-seguidores-kwai", "comprar-inscritos-youtube", "servicos"],
    ),
    dict(
        slug="como-comprar-seguidores",
        title="Como Comprar Seguidores com Segurança: Passo a Passo ({ano})",
        desc="Passo a passo para comprar seguidores no Instagram, TikTok, Kwai e YouTube com segurança: o que informar, o que nunca informar e como acompanhar a entrega.",
        h1="Como comprar seguidores com segurança",
        lead="O passo a passo completo, do que você precisa ter pronto antes até como pedir reposição depois.",
        body=[
            ("Antes de comprar", [
                ("ul", [
                    "Deixe o perfil público durante a entrega.",
                    "Tenha algumas publicações recentes: um perfil vazio com muitos seguidores chama atenção.",
                    "Separe o @ exato do perfil, ou o link do post ou vídeo, se o serviço for de curtidas ou visualizações.",
                ]),
            ]),
            ("Passo a passo", [
                ("ol", [
                    "<strong>Escolha a plataforma e o serviço.</strong> Seguidores, curtidas, visualizações ou inscritos.",
                    "<strong>Escolha o público e o ritmo.</strong> Brasileiros, gênero, nicho e entrega gradual ou rápida.",
                    "<strong>Informe o @ ou o link.</strong> Nunca a senha.",
                    "<strong>Pague via PIX.</strong> A confirmação é automática e o pedido começa em seguida.",
                    "<strong>Acompanhe pelo painel.</strong> Você vê quanto já foi entregue e pede reposição se algo cair.",
                ]),
            ]),
            ("O que nunca informar", [
                "Senha, código de verificação ou login por outro aplicativo. Nenhum serviço de seguidores precisa disso. Se um site pede, feche a página.",
            ]),
        ],
        faq=[
            ("Como comprar seguidores no Instagram?", "Escolha o pacote, informe o seu @ público e pague via PIX. A entrega começa em seguida, sem senha."),
            ("Como comprar seguidores no TikTok?", "Do mesmo jeito: informe o @ do perfil público, escolha a quantidade e pague. Os seguidores chegam no ritmo escolhido."),
            ("Posso comprar para outra pessoa?", "Pode. Basta informar o @ público do perfil que vai receber."),
        ],
        related=["guia/como-escolher-site-para-comprar-seguidores", "guia/vale-a-pena-comprar-seguidores", "comprar-seguidores-instagram", "comprar-seguidores-tiktok", "comprar-seguidores-kwai", "servicos"],
    ),
    dict(
        slug="como-saber-se-seguidores-sao-reais",
        title="Como Saber se os Seguidores São Reais ou Falsos: 6 Sinais",
        desc="Seis sinais para descobrir se seguidores são reais ou robôs, no seu perfil ou em qualquer outro. Inclui a conta de taxa de engajamento.",
        h1="Como saber se os seguidores são reais",
        lead="Seis sinais que qualquer pessoa consegue checar em poucos minutos, no seu perfil ou no de outra pessoa.",
        body=[
            ("Os 6 sinais", [
                ("ol", [
                    "<strong>Foto de perfil:</strong> contas sem foto, ou com fotos genéricas repetidas, são o sinal mais comum de perfil falso.",
                    "<strong>Publicações:</strong> perfis reais têm publicações; perfis falsos costumam ter zero ou poucas, todas no mesmo dia.",
                    "<strong>Proporção seguindo × seguidores:</strong> seguir milhares de contas e ter poucos seguidores é típico de robô.",
                    "<strong>Nome de usuário:</strong> sequências de letras e números aleatórios indicam contas criadas em massa.",
                    "<strong>Idioma e país:</strong> perfis brasileiros escrevem em português e seguem contas brasileiras.",
                    "<strong>Engajamento:</strong> muitos seguidores e quase nenhuma curtida são o sinal mais claro de números inflados.",
                ]),
            ]),
            ("Como calcular a taxa de engajamento", [
                "Some as curtidas e os comentários das últimas 10 publicações, divida por 10 e depois pelo número de seguidores. Multiplique por 100 para ter a porcentagem. Perfis pequenos costumam ficar entre 3% e 6%; perfis grandes, entre 1% e 3%. Muito abaixo disso indica seguidores que não interagem.",
            ]),
        ],
        faq=[
            ("Existe ferramenta para ver seguidores falsos?", "Existem ferramentas de auditoria, mas os seis sinais desta página resolvem a maioria dos casos sem instalar nada."),
            ("Seguidores comprados são falsos?", "Depende do serviço. Serviços internacionais baratos costumam entregar perfis vazios; serviços brasileiros de qualidade entregam perfis completos, que passam nos sinais acima."),
            ("Como remover seguidores falsos?", "No Instagram, dá para remover seguidores um a um pela lista. Vale fazer quando o engajamento está muito baixo."),
        ],
        related=["comprar-seguidores-reais", "comprar-seguidores-brasileiros", "guia/vale-a-pena-comprar-seguidores", "comprar-curtidas-instagram", "comprar-comentarios-instagram", "comprar-seguidores-instagram"],
    ),
    dict(
        slug="como-escolher-site-para-comprar-seguidores",
        title="Melhor Site para Comprar Seguidores: 7 Critérios para Escolher",
        desc="Como escolher um site confiável para comprar seguidores: 7 critérios, sinais de golpe e perguntas para fazer antes de pagar.",
        h1="Como escolher um site confiável para comprar seguidores",
        lead="Em vez de mais uma lista de “melhores sites”, os critérios para você mesmo avaliar qualquer site antes de pagar, incluindo o nosso.",
        body=[
            ("Os 7 critérios", [
                ("ol", [
                    "<strong>Não pede senha.</strong> Nunca, em nenhuma etapa.",
                    "<strong>Diz a origem dos perfis.</strong> Brasileiros ou internacionais, antes da compra.",
                    "<strong>Tem reposição por escrito.</strong> Com prazo definido e forma de pedir.",
                    "<strong>Mostra o preço antes do pagamento.</strong> Sem taxas surpresa no checkout.",
                    "<strong>Tem painel de acompanhamento.</strong> Você vê o que já foi entregue.",
                    "<strong>Tem suporte humano.</strong> Um canal em que alguém responde.",
                    "<strong>Não promete o impossível.</strong> Monetização garantida e seguidores que compram são promessas que ninguém controla.",
                ]),
            ]),
            ("Sinais de golpe", [
                ("ul", [
                    "Pede senha, código de verificação ou login por outro aplicativo.",
                    "Preços muito abaixo do mercado para seguidores “brasileiros e reais”.",
                    "Nenhuma política de reembolso ou de reposição.",
                    "Pagamento só por transferência para pessoa física.",
                ]),
            ]),
        ],
        faq=[
            ("Qual o site mais confiável para comprar seguidores?", "O que cumpre os sete critérios desta página. Teste com um pacote pequeno antes de fazer um pedido grande."),
            ("Como saber se um site de seguidores é golpe?", "Pedido de senha, preço bom demais e ausência de política de reposição são os três sinais mais comuns."),
            ("Pagar via PIX é seguro?", "É, quando o PIX vai para uma empresa com checkout identificado, e não para a conta de uma pessoa física."),
        ],
        related=["guia/como-comprar-seguidores", "guia/vale-a-pena-comprar-seguidores", "comprar-seguidores-instagram", "comprar-seguidores-reais", "comprar-seguidores-brasileiros", "servicos"],
    ),
]

# ----------------------------------------------------------------------------- layout

ICON_FOR_PLATFORM = {"Instagram": "ig", "TikTok": "tt", "YouTube": "yt", "Kwai": "kwai"}


def ic(root, name, cls=""):
    return f'<svg class="ic {cls}" aria-hidden="true"><use href="{root}assets/icons.svg#i-{name}"/></svg>'


def header(root):
    return f"""<header class="site-header">
  <div class="container nav">
    <a class="logo" href="{root}" aria-label="{BRAND}, início"><span class="brand-mark"></span><span>comprefácil<span class="logo-sub">seguidores</span></span></a>
    <nav class="nav-links" aria-label="Principal">
      <a href="{root}servicos/">Serviços</a>
      <a href="{root}#como">Como funciona</a>
      <a href="{root}#precos">Preços</a>
      <a href="{root}guia/">Guias</a>
    </nav>
    <div class="nav-actions">
      <a href="{root}painel/" class="btn btn-text btn-sm">Entrar</a>
      <a href="{root}#quiz" class="btn btn-primary btn-sm"><span class="lbl-long">Descobrir meu plano</span><span class="lbl-short">Começar</span></a>
    </div>
  </div>
</header>"""


def footer(root):
    top = ["comprar-seguidores-instagram", "comprar-seguidores-tiktok", "comprar-curtidas-instagram", "comprar-inscritos-youtube", "comprar-seguidores-kwai"]
    names = {p["slug"]: short_name(p) for p in SERVICES}
    links = "".join(f'<a class="d1" href="{root}{s}/">{names[s]}</a>' for s in top)
    return f"""<footer class="site-footer">
  <div class="container">
    <div class="foot-grid">
      <div class="foot-brand">
        <a class="logo" href="{root}"><span class="brand-mark"></span><span>comprefácil<span class="logo-sub">seguidores</span></span></a>
        <p class="d1 lgpd">{ic(root, 'shield')}<span>Sua privacidade está protegida. Seguimos a LGPD, criptografamos seus dados e nunca pedimos sua senha.</span></p>
      </div>
      <div class="fcol"><h4>Serviços</h4>{links}<a class="d1" href="{root}servicos/">Todos os serviços</a></div>
      <div class="fcol"><h4>Guias</h4><a class="d1" href="{root}guia/vale-a-pena-comprar-seguidores/">Vale a pena?</a><a class="d1" href="{root}guia/quanto-custa-1000-seguidores/">Quanto custa</a><a class="d1" href="{root}guia/como-comprar-seguidores/">Como comprar</a><a class="d1" href="{root}guia/">Todos os guias</a></div>
      <div class="fcol"><h4>Conta</h4><a class="d1" href="{root}painel/">Entrar</a><a class="d1" href="{root}painel/">Acompanhar pedido</a><a class="d1" href="{root}painel/">Indique e ganhe</a></div>
      <div class="fcol"><h4>Legal</h4><a class="d1" href="#">Privacidade (LGPD)</a><a class="d1" href="#">Termos de uso</a><a class="d1" href="#">Política de reembolso</a></div>
    </div>
    <div class="foot-bottom d1"><span>© {YEAR} {BRAND} · Preços atualizados em {TODAY.strftime('%d/%m/%Y')}, podem mudar.</span></div>
  </div>
</footer>"""


def layout(path, title, desc, body, jsonld=None, noindex=False):
    depth = path.count("/")
    root = "../" * depth
    canonical = BASE + path
    ld = "".join(f'\n<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (jsonld or []))
    robots = '<meta name="robots" content="noindex, follow">\n' if noindex else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{BASE}assets/icon-512.png">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" type="image/png" href="{root}assets/favicon.png">
<link rel="apple-touch-icon" href="{root}assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;600;700&display=swap">
<link rel="stylesheet" href="{root}assets/site.css?v={CSS_VERSION}">{ld}
</head>
<body>
{header(root)}
<main>
{body}
</main>
{footer(root)}
</body>
</html>
"""


def crumbs(root, trail):
    items = [f'<a href="{root}">Início</a>']
    for label, href in trail[:-1]:
        items.append(f'<a href="{root}{href}">{esc(label)}</a>')
    items.append(f'<span aria-current="page">{esc(trail[-1][0])}</span>')
    return '<nav class="crumbs d1" aria-label="Você está em">' + '<span class="sep">/</span>'.join(items) + "</nav>"


def crumbs_ld(trail):
    els = [{"@type": "ListItem", "position": 1, "name": "Início", "item": BASE}]
    for i, (label, href) in enumerate(trail, start=2):
        els.append({"@type": "ListItem", "position": i, "name": label, "item": BASE + href})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": els}


def faq_html(root, faq):
    items = "".join(f'<details{" open" if i == 0 else ""}><summary>{esc(q)}{ic(root, "plus")}</summary><p class="p2 ans">{esc(a)}</p></details>' for i, (q, a) in enumerate(faq))
    return f"""<section class="section" id="duvidas"><div class="container faq">
  <div><h2 class="h2">Dúvidas frequentes</h2><p class="p2 muted" style="margin-top:12px">As perguntas que mais aparecem nas buscas sobre este assunto.</p></div>
  <div class="faq-list">{items}</div>
</div></section>"""


def faq_ld(faq):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}


ALL_PAGES = {}  # slug -> (título curto, subtítulo) para os cards de relacionados


def short_name(p):
    unit = p.get("unit", "")
    return f"{unit.capitalize()} {p['plat']}" if unit and p.get("plat") else p["h1"]


def related_html(root, slugs):
    cards = []
    for s in slugs:
        if s == "servicos":
            name, sub = "Todos os serviços", "Catálogo completo por plataforma"
        else:
            name, sub = ALL_PAGES[s]
        cards.append(f'<a class="rel" href="{root}{s}/"><span><span class="p2 fw-semi">{esc(name)}</span><small>{esc(sub)}</small></span>{ic(root, "arrow-right")}</a>')
    return f'<section class="section"><div class="container"><h2 class="h3">Veja também</h2><div class="related">{"".join(cards)}</div></div></section>'


def cta_href(root, page):
    if page.get("quiz"):
        return f"{root}?plataforma={page['quiz']}#quiz", "Descobrir meu plano"
    return f"{root}painel/?servico={page['slug']}", "Fazer pedido"


def prose_blocks(blocks, fill=None):
    out = []
    for b in blocks:
        if isinstance(b, tuple):
            kind, items = b
            out.append(f"<{kind}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{kind}>")
        elif fill and b in fill:
            out.append(fill[b])
        else:
            out.append(f"<p>{b}</p>")
    return "".join(out)

# ----------------------------------------------------------------------------- páginas

def fmt_all(obj, t):
    if isinstance(obj, str):
        return obj.format(**t)
    if isinstance(obj, tuple):
        return tuple(fmt_all(x, t) for x in obj)
    if isinstance(obj, list):
        return [fmt_all(x, t) for x in obj]
    if isinstance(obj, dict):
        return {k: fmt_all(v, t) for k, v in obj.items()}
    return obj


def render_service(p):
    svc = pick(**p["svc"])
    p["_svc"] = svc
    t = tokens(svc, p["unit"])
    c = fmt_all({k: p[k] for k in ("title", "desc", "h1", "lead", "intro", "why", "faq") if k in p}, t)
    note = p.get("note")
    path = p["slug"] + "/"
    root = "../"
    href, label = cta_href(root, p)
    trail = [("Serviços", "servicos/"), (short_name(p), path)]
    pk = [] if p.get("no_packages") else packages(svc)

    facts = [("users", t["origem"]), ("refresh", t["reposicao"])]
    if t["tempo"]:
        facts.append(("clock", f"Tempo médio: {t['tempo']}"))
    facts.append(("shield", "Sem senha"))
    facts_html = "".join(f'<span class="fact">{ic(root, i)}{esc(x)}</span>' for i, x in facts)

    if pk:
        pop = min(2, len(pk) - 1)
        cards = "".join(
            f'<div class="pkg{" pop-pkg" if i == pop else ""}">'
            + (f'<span class="po-badge">{ic(root, "star", "fill")}Mais escolhido</span>' if i == pop else "")
            + f'<span class="qty num">+{num(x["qty"])}</span><span class="unit d1">{esc(p["unit"])}</span>'
            + f'<span class="price">{brl(x["price"])}</span><span class="t1 muted">{brl(x["price"] / x["qty"] * 1000)} por mil</span>'
            + f'<a class="btn {"btn-primary" if i == pop else "btn-outline"}" href="{href}">{label}</a></div>'
            for i, x in enumerate(pk))
        pkg_html = f"""<section class="section" id="pacotes"><div class="container">
  <h2 class="h2">Pacotes de {esc(p['unit'])} no {esc(p['plat'])}</h2>
  <div class="pkgs">{cards}</div>
  <p class="pkg-note d1">Precisa de outra quantidade? No painel você escolhe qualquer valor entre {num(svc['min'])} e {num(svc['max'])}. Preços em reais, pagamento via PIX.</p>
</div></section>"""
    else:
        pkg_html = ""

    why = "".join(f'<div class="why-item"><span class="f-ic f-{["navy", "yellow", "peach"][i % 3]}">{ic(root, w[0])}</span><h3 class="h5">{esc(w[1])}</h3><p class="p2 muted">{esc(w[2])}</p></div>' for i, w in enumerate(c["why"]))
    intro = "".join(f"<p>{esc(x)}</p>" for x in c["intro"])
    note_html = f'<div class="callout-box warn d1">{ic(root, "info")} {esc(note)}</div>' if note else ""
    price_line = f'<p class="p2" style="margin-top:20px">A partir de <strong class="h4">{brl(pk[0]["price"])}</strong> <span class="muted">· {brl(price_for(svc, 1000))} por 1.000</span></p>' if pk else ""

    body = f"""<section class="page-hero"><div class="container">
  {crumbs(root, trail)}
  <h1 class="h1">{esc(c['h1'])}</h1>
  <p class="p1">{esc(c['lead'])}</p>
  <div class="facts">{facts_html}</div>
  {price_line}
  <div class="page-cta"><a class="btn btn-primary btn-lg" href="{href if not pk else '#pacotes'}">{'Ver pacotes' if pk else label} {ic(root, 'arrow-right')}</a><a class="btn btn-secondary btn-lg" href="#duvidas">Tirar dúvidas</a></div>
</div></section>
{pkg_html}
<section class="section"><div class="container">
  <h2 class="h2">Por que comprar {esc(p['unit'])} no {esc(p['plat'])} aqui</h2>
  <div class="why">{why}</div>
</div></section>
<section class="section"><div class="container layout-2">
  <article class="prose">
    <h2 style="margin-top:0">O que muda quando você compra {esc(p['unit'])} no {esc(p['plat'])}</h2>
    {note_html}{intro}
    <h2>Como funciona o pedido</h2>
    <ol><li><strong>Escolha o pacote</strong> ou a quantidade exata no painel.</li><li><strong>Informe o @ ou o link público.</strong> Nunca a senha.</li><li><strong>Pague via PIX.</strong> A confirmação é automática e o pedido começa em seguida.</li><li><strong>Acompanhe a entrega</strong> e peça reposição pelo painel, se precisar.</li></ol>
  </article>
  <aside class="aside-card">
    <p class="t1 upper fw-bold muted">Resumo do serviço</p>
    <p class="h5" style="margin-top:6px">{esc(short_name(p))}</p>
    <ul>{"".join(f"<li>{ic(root, 'check')}<span>{esc(x)}</span></li>" for _, x in facts)}</ul>
    <a class="btn btn-primary" href="{href}">{label}</a>
  </aside>
</div></section>
{faq_html(root, c['faq'])}
{related_html(root, p['related'])}"""

    ld = [crumbs_ld(trail), faq_ld(c["faq"])]
    if pk:
        ld.append({"@context": "https://schema.org", "@type": "Product", "name": c["h1"], "description": c["desc"],
                   "brand": {"@type": "Brand", "name": BRAND}, "image": BASE + "assets/icon-512.png",
                   "offers": {"@type": "AggregateOffer", "priceCurrency": "BRL", "lowPrice": f"{pk[0]['price']:.2f}",
                              "highPrice": f"{pk[-1]['price']:.2f}", "offerCount": len(pk), "availability": "https://schema.org/InStock"}})
    return path, layout(path, c["title"], c["desc"], body, ld)


def br_table(root):
    rows = []
    for s in ["comprar-seguidores-instagram", "comprar-seguidores-tiktok", "comprar-seguidores-kwai"]:
        p = next(x for x in SERVICES if x["slug"] == s)
        svc = p["_svc"]
        rows.append(f'<tr><td><a href="{root}{s}/">{p["plat"]}</a></td><td class="num">{brl(price_for(svc, 1000))}</td><td>{refill_txt(svc)}</td></tr>')
    return '<div class="table-wrap"><table><thead><tr><th>Plataforma</th><th class="num">1.000 seguidores brasileiros</th><th>Reposição</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


def cheap_table(root):
    rows = []
    for p in SERVICES:
        if p.get("no_packages") or p["unit"] not in ("seguidores", "inscritos"):
            continue
        svc = p["_svc"]
        rows.append((price_for(svc, 1000), f'<tr><td><a href="{root}{p["slug"]}/">{short_name(p)}</a></td><td class="num">{brl(packages(svc)[0]["price"])}</td><td class="num">{brl(price_for(svc, 1000))}</td><td>{"Brasileiros" if svc["br"] else "Internacionais"}</td></tr>'))
    rows.sort(key=lambda r: r[0])
    return '<div class="table-wrap"><table><thead><tr><th>Serviço</th><th class="num">Menor pacote</th><th class="num">Por 1.000</th><th>Origem</th></tr></thead><tbody>' + "".join(r for _, r in rows) + "</tbody></table></div>"


def price_table(root):
    rows = []
    for p in SERVICES:
        if p.get("no_packages"):
            continue
        svc = p["_svc"]
        rows.append(f'<tr><td><a href="{root}{p["slug"]}/">{short_name(p)}</a></td><td class="num">{brl(price_for(svc, 1000))}</td><td>{"Brasileiros" if svc["br"] else "Internacionais"}</td><td>{refill_txt(svc)}</td></tr>')
    return '<div class="table-wrap"><table><thead><tr><th>Serviço</th><th class="num">Por 1.000</th><th>Origem</th><th>Reposição</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


def render_intent(p):
    path = p["slug"] + "/"
    root = "../"
    t = {"ano": YEAR}
    c = fmt_all({k: p[k] for k in ("title", "desc", "h1", "lead", "faq")}, t)
    trail = [("Serviços", "servicos/"), (c["h1"], path)]
    table = br_table(root) if p["kind"] == "br" else cheap_table(root)
    sections = "".join(f"<h2{' style=\"margin-top:0\"' if i == 0 else ''}>{esc(h)}</h2>{prose_blocks(b)}" for i, (h, b) in enumerate(p["body"]))
    body = f"""<section class="page-hero"><div class="container">
  {crumbs(root, trail)}
  <h1 class="h1">{esc(c['h1'])}</h1>
  <p class="p1">{esc(c['lead'])}</p>
  <div class="page-cta"><a class="btn btn-primary btn-lg" href="{root}#quiz">Descobrir meu plano {ic(root, 'arrow-right')}</a><a class="btn btn-secondary btn-lg" href="#tabela">Ver preços</a></div>
</div></section>
<section class="section"><div class="container">
  <article class="prose">
    {sections}
    <h2 id="tabela">Preços</h2>
    {table}
  </article>
</div></section>
{faq_html(root, c['faq'])}
{related_html(root, p['related'])}"""
    return path, layout(path, c["title"], c["desc"], body, [crumbs_ld(trail), faq_ld(c["faq"])])


def render_guide(g):
    path = f"guia/{g['slug']}/"
    root = "../../"
    ig = next(x for x in SERVICES if x["slug"] == "comprar-seguidores-instagram")["_svc"]
    kw = next(x for x in SERVICES if x["slug"] == "comprar-seguidores-kwai")["_svc"]
    t = {"ano": YEAR, "data": TODAY.strftime("%d/%m/%Y"), "ig_mil": brl(price_for(ig, 1000)), "kwai_mil": brl(price_for(kw, 1000))}
    c = fmt_all({k: g[k] for k in ("title", "desc", "h1", "lead", "faq")}, t)
    trail = [("Guias", "guia/"), (c["h1"], path)]
    fill = {"__PRICE_TABLE__": price_table(root)}
    sections = "".join(f"<h2{' style=\"margin-top:0\"' if i == 0 else ''}>{esc(h)}</h2>{prose_blocks(b, fill)}" for i, (h, b) in enumerate(g["body"]))
    body = f"""<section class="page-hero"><div class="container">
  {crumbs(root, trail)}
  <h1 class="h1">{esc(c['h1'])}</h1>
  <p class="p1">{esc(c['lead'])}</p>
  <p class="d1 muted" style="margin-top:16px">Atualizado em {TODAY.strftime('%d/%m/%Y')}</p>
</div></section>
<section class="section" style="padding-top:56px"><div class="container layout-2">
  <article class="prose">{sections}</article>
  <aside class="aside-card">
    <p class="t1 upper fw-bold muted">Pronto para começar?</p>
    <p class="h5" style="margin-top:6px">Monte seu plano em 1 minuto</p>
    <ul><li>{ic(root, 'check')}<span>Seguidores brasileiros do seu nicho</span></li><li>{ic(root, 'check')}<span>Entrega gradual, sem senha</span></li><li>{ic(root, 'check')}<span>Pagamento via PIX</span></li></ul>
    <a class="btn btn-primary" href="{root}#quiz">Descobrir meu plano</a>
  </aside>
</div></section>
{faq_html(root, c['faq'])}
{related_html(root, g['related'])}"""
    art = {"@context": "https://schema.org", "@type": "Article", "headline": c["h1"], "description": c["desc"],
           "datePublished": TODAY.isoformat(), "dateModified": TODAY.isoformat(), "inLanguage": "pt-BR",
           "author": {"@type": "Organization", "name": BRAND}, "publisher": {"@type": "Organization", "name": BRAND, "logo": {"@type": "ImageObject", "url": BASE + "assets/icon-512.png"}},
           "mainEntityOfPage": BASE + path}
    return path, layout(path, c["title"], c["desc"], body, [crumbs_ld(trail), art, faq_ld(c["faq"])])


def render_services_hub():
    path = "servicos/"
    root = "../"
    groups = {}
    for p in SERVICES:
        groups.setdefault(p["plat"], []).append(p)
    blocks = []
    for plat, ps in groups.items():
        cards = []
        for p in ps:
            svc = p["_svc"]
            sub = "Guia de monetização" if p.get("no_packages") else f"A partir de {brl(packages(svc)[0]['price'])} · {'brasileiros' if svc['br'] else 'internacionais'}"
            cards.append(f'<a class="rel" href="{root}{p["slug"]}/"><span><span class="p2 fw-semi">{esc(short_name(p))}</span><small>{esc(sub)}</small></span>{ic(root, "arrow-right")}</a>')
        icon = ICON_FOR_PLATFORM.get(plat, "users")
        blocks.append(f'<div class="hub-group"><h2 class="h4">{ic(root, icon)}{esc(plat)}</h2><div class="related">{"".join(cards)}</div></div>')
    intents = "".join(f'<a class="rel" href="{root}{p["slug"]}/"><span><span class="p2 fw-semi">{esc(p["h1"])}</span><small>{esc(p["lead"][:70])}…</small></span>{ic(root, "arrow-right")}</a>' for p in INTENT)
    trail = [("Serviços", path)]
    body = f"""<section class="page-hero"><div class="container">
  {crumbs(root, trail)}
  <h1 class="h1">Todos os serviços</h1>
  <p class="p1">Seguidores, curtidas, visualizações, inscritos e membros para {len(groups)} plataformas. Preços em reais, pagamento via PIX e nenhuma senha.</p>
</div></section>
<section class="section" style="padding-top:24px"><div class="container">
  <div class="hub-group"><h2 class="h4">{ic(root, 'star')}Mais procurados</h2><div class="related">{intents}</div></div>
  {"".join(blocks)}
</div></section>"""
    title = "Comprar Seguidores, Curtidas e Visualizações | CompreFácil"
    desc = f"Catálogo completo: seguidores, curtidas, visualizações e inscritos para Instagram, TikTok, Kwai, YouTube e mais {len(groups) - 4} plataformas, com PIX."
    return path, layout(path, title, desc, body, [crumbs_ld(trail)])


def render_guides_hub():
    path = "guia/"
    root = "../"
    cards = "".join(f'<a class="guide-card" href="{root}guia/{g["slug"]}/"><span class="h5">{esc(g["h1"].format(ano=YEAR))}</span><span class="p2 muted">{esc(g["lead"].format(ano=YEAR, data=TODAY.strftime("%d/%m/%Y")))}</span><span class="d1 fw-semi" style="color:var(--blue)">Ler guia →</span></a>' for g in GUIDES)
    trail = [("Guias", path)]
    body = f"""<section class="page-hero"><div class="container">
  {crumbs(root, trail)}
  <h1 class="h1">Guias</h1>
  <p class="p1">Respostas diretas para as dúvidas mais buscadas sobre comprar seguidores: segurança, preço, passo a passo e como identificar perfis falsos.</p>
</div></section>
<section class="section" style="padding-top:24px"><div class="container"><div class="guide-list">{cards}</div></div></section>"""
    return path, layout(path, f"Guias sobre Comprar Seguidores | {BRAND}", "Guias com respostas diretas: vale a pena comprar seguidores, quanto custa, como comprar com segurança e como saber se os seguidores são reais.", body, [crumbs_ld(trail)])


def render_panel_placeholder():
    path = "painel/"
    root = "../"
    body = f"""<section class="page-hero"><div class="container" style="max-width:640px;padding-block:80px;text-align:center">
  <span class="brand-mark lg" aria-hidden="true" style="margin:0 auto"></span>
  <h1 class="h2" style="margin-top:24px">O painel está chegando</h1>
  <p class="p1">Em breve você entra aqui para fazer pedidos de qualquer serviço, acompanhar entregas, pedir reposição e ganhar créditos indicando amigos.</p>
  <div class="page-cta" style="justify-content:center"><a class="btn btn-primary btn-lg" href="{root}#quiz">Descobrir meu plano</a><a class="btn btn-secondary btn-lg" href="{root}servicos/">Ver serviços</a></div>
</div></section>"""
    return path, layout(path, f"Painel | {BRAND}", "Painel de pedidos do CompreFácil Seguidores.", body, noindex=True)

# ----------------------------------------------------------------------------- build


def write(path, content):
    out = ROOT / path / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def main():
    for p in SERVICES:
        p["_svc"] = pick(**p["svc"])
        ALL_PAGES[p["slug"]] = (short_name(p), "Guia de monetização" if p.get("no_packages") else f"A partir de {brl(packages(p['_svc'])[0]['price'])}")
    for p in INTENT:
        ALL_PAGES[p["slug"]] = (p["h1"], "Preços e comparação por plataforma")
    for g in GUIDES:
        ALL_PAGES["guia/" + g["slug"]] = (g["h1"].format(ano=YEAR), "Guia")

    built = []
    for fn, items in ((render_service, SERVICES), (render_intent, INTENT), (render_guide, GUIDES)):
        for item in items:
            path, content = fn(item)
            write(path, content)
            built.append(path)
    for fn in (render_services_hub, render_guides_hub):
        path, content = fn()
        write(path, content)
        built.append(path)
    path, content = render_panel_placeholder()
    write(path, content)

    urls = [""] + built
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        prio = "1.0" if u == "" else "0.8" if u.startswith("comprar-") else "0.6"
        sm.append(f"  <url><loc>{BASE}{u}</loc><lastmod>{TODAY.isoformat()}</lastmod><priority>{prio}</priority></url>")
    sm.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /painel/\n\nSitemap: {BASE}sitemap.xml\n", encoding="utf-8")

    print(f"{len(built)} páginas indexáveis + painel (noindex), sitemap com {len(urls)} URLs\n")
    for p in SERVICES:
        s = p["_svc"]
        pk = "sem pacotes" if p.get("no_packages") else " · ".join(f"{num(x['qty'])}={brl(x['price'])}" for x in packages(s))
        print(f"  {p['slug']:<36} #{s['id']:<5} {'BR ' if s['br'] else 'INT'} {refill_txt(s):<20} {pk}")


if __name__ == "__main__":
    main()
