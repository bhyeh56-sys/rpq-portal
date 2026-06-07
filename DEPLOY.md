# RPQ Portal Deployment

## Domain Policy

`redpinequant.com` is the main RedPine Quant company website. It serves the company overview and selection screen:

- `https://redpinequant.com/`
- `https://redpinequant.com/risk`
- `https://redpinequant.com/faq`

`https://redpinequant.com/copy` is the Global Prime GP Copy information page.

`https://redpinequant.com/fund` serves the same participation review page used by the fund review domain.

`rpqtfund.com` is an independent participation review site for investment association or fund-style inquiries. It must not redirect to `https://redpinequant.com/copy`.

`rpqfund.com` is not used.

## Nginx Overview

The `redpinequant.com` server block should terminate TLS and proxy requests to the RPQ Portal FastAPI service.

The `rpqtfund.com` and `www.rpqtfund.com` server blocks should also proxy to the same FastAPI service. The application uses the `Host` header to render `templates/fund.html` for:

- `rpqtfund.com`
- `www.rpqtfund.com`

Do not configure `rpqtfund.com` or `www.rpqtfund.com` as a redirect to `/copy`.

Keep admin, portal, database, and investor functionality separate from the public domain policy.

## Certbot Domains

The public certificates should cover:

- `redpinequant.com`
- `www.redpinequant.com` if the `www` hostname is enabled
- `rpqtfund.com`
- `www.rpqtfund.com`

Do not request certificates for unused domains.

## Smoke Test

Run the production smoke test from the repository root:

```bash
bash scripts/smoke_prod.sh
```

By default it checks:

- `GET https://redpinequant.com/` returns `200`
- `GET https://redpinequant.com/copy` returns `200`
- `GET https://redpinequant.com/risk` returns `200`
- `GET https://redpinequant.com/faq` returns `200`
- `GET https://redpinequant.com/fund` returns `200`
- `GET https://rpqtfund.com/` returns `200`
- `GET https://www.rpqtfund.com/` returns `200`
- `rpqtfund.com` responses do not redirect to `https://redpinequant.com/copy`

Use `BASE_URL` only when checking a staging instance of the primary public site:

```bash
BASE_URL=https://staging.example.com bash scripts/smoke_prod.sh
```
