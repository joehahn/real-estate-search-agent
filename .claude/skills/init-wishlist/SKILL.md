---
name: init-wishlist
description: Onboard a new user by creating a personalized wishlist.md through a short interview, then validate it parses. Run this before the first /search-homes.
---

# /init-wishlist

Create or refine the user's `wishlist.md`. The wishlist is the single source of truth for
the search: hard filters and scoring weights in its YAML block, prose preferences below.

## Steps

1. If `wishlist.md` already exists, read it and ask the user what they want to change
   rather than overwriting. Otherwise copy `wishlist.example.md` to `wishlist.md` as a
   starting point.

2. Interview the user for the fields that need real values. Ask in plain language, a few
   at a time, not as a wall of questions:
   - Where do you want to search? Accept either a region in plain words (for example
     "West Knoxville, TN") or specific zip codes. If they give a region, expand it into a
     concrete zip list with your geographic knowledge, set both `region` and `zip_codes`,
     and show them the zips so they can trim. One RentCast call per zip; 3 to 8 is a good
     range for the free tier.
   - Price ceiling? Any floor?
   - Minimum bedrooms and bathrooms?
   - Minimum lot size in acres? (0 to ignore)
   - Property types? (Single Family, Condo, Townhouse, Manufactured, Multi-Family, Land)
   - What matters most: a low price, more land, more house, a fresh listing? (this sets
     the scoring weights)
   - Any must-haves, nice-to-haves, or hard deal-breakers? (flood plain, HOA cap,
     highway frontage, schools, foundation issues, etc.)
   - What does your daily life look like? Commute target, kids, walkability? (this feeds
     the analyst's location judgment)

3. Write the answers into `wishlist.md`: structured answers into the YAML block, the
   qualitative answers into the Must-haves / Nice-to-haves / Deal-breakers /
   Lifestyle sections. Normalize weights to sum near 1.0 but it is not required; the
   scorer normalizes internally.

4. Validate it parses:
   ```bash
   source .venv/bin/activate
   python -c "from src.wishlist import load_wishlist; w=load_wishlist(); print('OK:', w.zip_codes, 'price<=', w.price_max, 'weights', w.weights)"
   ```
   If it raises, fix the YAML block and re-run.

5. Tell the user they are ready to run `/search-homes`, and remind them the search step
   needs `RENTCAST_API_KEY` in the environment (free key at https://app.rentcast.io/app/api).

## Notes

- `wishlist.md` is gitignored. The user's personal search stays private; only
  `wishlist.example.md` is committed.
- Do not put the user's real criteria into `wishlist.example.md`.
