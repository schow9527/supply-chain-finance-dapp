# docs/design-EN · Member 5 Deliverables (English Version)

> English version of all Member 5 (Design & Presentation) deliverables, mirroring `docs/designs/`:
> **UI wireframes (reference for Member 3), the 5 required diagram types, demo deck, and user manual.**

## Structure

```
docs/design-EN/
├── README.md                  ← this file
├── diagrams/                  ← the 5 required diagram types (mermaid sources + PNG exports)
│   ├── 01-system-architecture.mmd / .png    System architecture (4 layers)
│   ├── 02-contract-interaction.mmd / .png   Contract interaction (on-chain sequence)
│   ├── 03-data-model.mmd / .png             Data model (ER, 7 tables)
│   ├── 04-business-flow.mmd / .png          Business flow (with exception branches)
│   ├── 05-ui-navigation.mmd / .png          UI navigation (19 pages)
│   └── README.md                            Index with renderable mermaid sources
├── wireframes/                ← 19 page wireframes (1:1 with PRD Sec.8 page list)
│   └── README.md                            Index + layout & interaction specs
├── presentation/
│   └── scf-dapp-demo-en/      ← English demo deck source (kimi-slides .pptd, 13 pages)
└── user-manual/
    └── User-Manual.md         ← Full manual for the five roles + troubleshooting
```

## Notes

1. **Diagrams**: `.mmd` files are mermaid sources (rendered natively by GitHub, editable); `.png` files are exports for reports and slides.
2. **Wireframes**: implementation reference for the frontend; red annotations map to PRD acceptance feature IDs (F-xx).
3. **Deck**: open the `.pptd` project in Kimi Work to edit, and export `.pptx` from the editor. The closing slide carries the full team division of labor.
4. **User manual**: end-user documentation for all five roles.

## Cross-references (data stays identical across languages)

| Source (repo) | Used by |
| :--- | :--- |
| `contracts/docs/interface.md`, `contracts/abi/` | diagrams 01/02, deck pp.5/7 |
| `contracts/docs/gas/` (Foundry benchmarks) | deck p.11 |
| `contracts/deployments/11155111.json` | deck p.12 |
| `docs/PRD.md` Sec.7.2 API list | diagram 03, deck p.10 |

The Chinese versions live in `docs/designs/`; content is kept in sync between the two folders.
