---
description: Create an Outlook contact from freeform text (business card, email signature, address block)
skill: contact-creator
---

# Kontakt erstellen

**This command activates the `contact-creator` skill** to create Outlook contacts from freeform text.

## Usage

If the user provided contact information with this command, proceed immediately.
If no contact information was provided, ask the user to paste the contact details.

## What to do

**Follow the complete workflow documented in the `contact-creator` skill**:

1. **Verify MS365 login** (`mcp__ms365__login`)
2. **Extract contact information** from the freeform text
3. **Structure the data** according to MS365 API requirements (see `references/contact_fields.md` in the skill)
4. **Create the contact** via `mcp__ms365__create-outlook-contact`
5. **Display confirmation** with all saved details

## Important Notes

- Parse ALL available information: name, title, position, company, phones, email, address, website
- German contacts often have titles (Dr., Prof.) - include these
- Fax numbers go in `personalNotes` (API limitation)
- Confirm that the contact will sync to mobile devices automatically

**For complete field specifications and examples, refer to the `contact-creator` skill documentation.**
