# CompreFácil Seguidores

Plataforma de venda de seguidores brasileiros por nicho, com pagamento via PIX. Os pedidos são processados pela API do BRSMM.

## Status

**Prévia de design** (`index.html`): landing page + onboarding gamificado de 13 perguntas → processamento → resultado com projeção → paywall com 3 planos calculados a partir da meta.

Números, depoimentos e o feed "ao vivo" da prévia são ilustrativos e precisam ser trocados por dados reais antes do lançamento.

## Páginas de SEO

31 páginas indexáveis geradas por `tools/gerar_paginas.py`: 21 de serviço (plataforma × serviço), 3 de intenção (brasileiros, reais, baratos), 5 guias e os hubs `/servicos/` e `/guia/`, mais `sitemap.xml` e `robots.txt`.

O gerador lê `data/catalogo_precos.csv` (custo do BRSMM × 2,3), que fica **fora do git** para não expor a margem. Sempre que o catálogo mudar:

```bash
python3 tools/gerar_paginas.py
```

Ao trocar para um domínio próprio, altere `BASE` no gerador e o `canonical` do `index.html`.

## Ver localmente

Abra o `index.html` no navegador. Não precisa de build.

## Próximos passos

1. Aprovar o visual
2. Design system (tokens de cor e tipografia + componentes)
3. App real: contas/login, painel do usuário, indicação, painel de receita, PIX (Mercado Pago), integração com o BRSMM
4. Páginas de SEO

## Design

- Paleta: `#010012` `#002A5C` `#0E5DA0` `#FFC7AC` `#FFED97` `#DF309F`
- Fonte: Source Sans 3 (escala H1 64 → t1 12, do Figma)
- Ícones: Phosphor (peso bold)
- Logo (coroa, PNG transparente): `assets/logo.png` em resolução cheia, `assets/logo-256.png` para a interface; favicon, apple-touch-icon e `icon-512.png` na mesma pasta
