# Ecommerce brand template

Use for a storefront or direct-to-consumer brand. The example brand, URLs, and findings are fictional. Capture the actual product range and buying path; do not assume that a public product page proves checkout access or a completed purchase.

## `config.yaml`

```yaml
id: small-desk-supply
name: Small Desk Supply
description: Desk organizers designed for compact workspaces.
website:
  status: verified
  url: https://small-desk-supply.example/
channels:
  newsletter:
    status: verified
    url: https://small-desk-supply.example/newsletter
    signup_url: https://small-desk-supply.example/newsletter/signup
palette:
  ink: "#222725"
  background: "#F6F3EB"
knowledge_base_file: knowledge-base.md
```

## `knowledge-base.md`

```markdown
# Small Desk Supply brand knowledge

- Audience and offer: The [collection](https://small-desk-supply.example/collections/compact-desks) is positioned for shoppers with limited desk space. Cite exact dimensions and materials on the relevant product pages.
- Conversion: The public flow runs from collection to product to cart. Checkout and purchase tracking were not tested. The [shipping policy](https://small-desk-supply.example/shipping) defines eligible destinations and is the source for shipping claims.
- Visual identity: The palette reflects the observed storefront. Product photos are visual references unless the brand confirms reuse rights; record permission for any files you save.
- Open questions: Confirm the priority collection, markets the store can fulfill, approved claims, and who can grant access to aggregate order data.
```

If you capture the storefront, add `screenshots` entries only after the files are saved and verified. Reference actual reusable product images under `images/` only after checking rights. Document capture sources and reuse terms in `design/assets.md`, separately from the marketing knowledge above.
