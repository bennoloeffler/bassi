# Microsoft 365 Contact Fields Reference

This document provides detailed specifications for all contact fields supported by the MS365 API via `mcp__ms365__create-outlook-contact`.

## Required Fields

### displayName (string)
The contact's display name. This is the primary name shown in Outlook and mobile contacts.

**Examples:**
- "Dr. Mathias Bach"
- "Thomas Herrmann"
- "Anna Schmidt"

**Best practices:**
- Include titles (Dr., Prof.) in the display name
- Use the full formal name
- This field determines how the contact appears in contact lists

### emailAddresses (array)
Array of email address objects. At least one email address is required.

**Structure:**
```json
{
  "emailAddresses": [
    {
      "name": "Dr. Mathias Bach",
      "address": "mathias.bach@herrmannultraschall.com"
    }
  ]
}
```

**Fields:**
- `name` - Display name for this email address (usually same as displayName)
- `address` - The email address (validated as email format)

## Name Fields

### givenName (string)
First name of the contact.

**Example:** "Mathias"

### surname (string)
Last name of the contact.

**Example:** "Bach"

### title (string)
Academic or professional title prefix.

**Examples:**
- "Dr."
- "Prof."
- "Prof. Dr."

### middleName (string)
Middle name of the contact.

### nickName (string)
Informal name or nickname.

## Organization Fields

### companyName (string)
Name of the organization or company.

**Example:** "Herrmann Ultraschalltechnik GmbH & Co. KG"

### jobTitle (string)
Position or role within the organization.

**Examples:**
- "Leiter Forschung & Entwicklung"
- "Eigentümer - Aufsichtsrat und ex CEO"
- "Senior Software Engineer"

### department (string)
Department within the organization.

**Example:** "Research & Development"

### officeLocation (string)
Physical office location.

**Example:** "Building A, Floor 3"

## Phone Numbers

### businessPhones (array of strings)
Business phone numbers. Can include multiple numbers.

**Format:** Any string format is accepted, formatting is preserved.

**Examples:**
```json
{
  "businessPhones": ["+49 175 2043181"]
}
```

```json
{
  "businessPhones": [
    "+49 (7248) 79 1097",
    "+49 (7248) 79 1098"
  ]
}
```

**Note:** Mobile numbers should also go in this array, as the API doesn't consistently expose a separate mobile field.

### homePhones (array of strings)
Home phone numbers.

### mobilePhone (string)
Mobile phone number (single value, not array).

**Note:** Prefer using `businessPhones` for reliability across different Outlook clients.

## Address Fields

### businessAddress (object)
Business address structured as an object.

**Structure:**
```json
{
  "businessAddress": {
    "street": "Descostraße 3-11",
    "city": "Karlsbad",
    "postalCode": "76307",
    "countryOrRegion": "Germany",
    "state": ""
  }
}
```

**Fields:**
- `street` - Street address
- `city` - City name
- `postalCode` - Postal/ZIP code
- `countryOrRegion` - Country name (use full name, e.g., "Germany" not "DE")
- `state` - State or province (optional, mainly for US addresses)

### homeAddress (object)
Home address with same structure as businessAddress.

## Web and Messaging

### businessHomePage (string)
Company website or homepage.

**Format:** URL without or with protocol.

**Examples:**
- "www.herrmannultraschall.com"
- "https://www.example.com"

**Note:** Both formats work, but without protocol is more common.

### imAddresses (array of strings)
Instant messaging addresses (Skype, Teams, etc.).

**Example:**
```json
{
  "imAddresses": ["skype:john.doe"]
}
```

## Personal Information

### birthday (string, ISO 8601 date-time)
Contact's birthday.

**Format:** "YYYY-MM-DDTHH:mm:ss.sssZ"

**Example:** "2014-01-01T00:00:00Z"

### spouseName (string)
Name of spouse.

### children (array of strings)
Names of children.

## Categories and Notes

### categories (array of strings)
Categories for organizing contacts.

**Example:**
```json
{
  "categories": ["Business", "Suppliers"]
}
```

### personalNotes (string)
Freeform notes about the contact.

**Use case:** Store information not fitting other fields, like fax numbers.

**Example:**
```json
{
  "personalNotes": "Fax: +49 (7248) 79 1017"
}
```

## Assistant and Manager

### assistantName (string)
Name of the contact's assistant.

### manager (string)
Name of the contact's manager.

## Read-Only Fields

The following fields are set by the system and cannot be specified during contact creation:

- `id` - Unique identifier
- `createdDateTime` - Creation timestamp
- `lastModifiedDateTime` - Last modification timestamp
- `changeKey` - Version identifier for optimistic concurrency
- `parentFolderId` - Parent folder identifier
- `fileAs` - Filing name (auto-generated)

## Field Limitations

### Fax Numbers
**Not supported** via the standard API contact fields. Fax numbers cannot be stored in a dedicated field.

**Workaround:** Store fax numbers in `personalNotes`:
```json
{
  "personalNotes": "Fax: +49 (7248) 79 1017"
}
```

### Multiple Email Addresses
Fully supported via the `emailAddresses` array. Each entry needs both `name` and `address`.

### Phone Number Formatting
Phone numbers are stored as strings without validation. Any formatting is preserved:
- "+49 175 2043181" ✓
- "+49 (7248) 79 1097" ✓
- "0175 2043181" ✓

## Common Patterns

### German Business Contact (Full Example)
```json
{
  "givenName": "Mathias",
  "surname": "Bach",
  "title": "Dr.",
  "displayName": "Dr. Mathias Bach",
  "jobTitle": "Leiter Forschung & Entwicklung",
  "companyName": "Herrmann Ultraschalltechnik GmbH & Co. KG",
  "businessPhones": ["+49 175 2043181"],
  "emailAddresses": [
    {
      "address": "mathias.bach@herrmannultraschall.com",
      "name": "Dr. Mathias Bach"
    }
  ],
  "businessAddress": {
    "street": "Descostr. 3-11",
    "city": "Karlsbad",
    "postalCode": "76307",
    "countryOrRegion": "Germany"
  },
  "businessHomePage": "www.herrmannultraschall.com"
}
```

### Minimal Contact
```json
{
  "displayName": "Anna Schmidt",
  "emailAddresses": [
    {
      "address": "anna.schmidt@example.com",
      "name": "Anna Schmidt"
    }
  ]
}
```

### Contact with Multiple Phones
```json
{
  "displayName": "John Doe",
  "emailAddresses": [
    {
      "address": "john.doe@example.com",
      "name": "John Doe"
    }
  ],
  "businessPhones": [
    "+1 555 1234 (Office)",
    "+1 555 5678 (Mobile)"
  ]
}
```

## Validation Rules

1. **displayName** - Must be non-empty string
2. **emailAddresses** - Must contain at least one valid email object
3. **email address** - Must be valid email format (name@domain.tld)
4. **phone numbers** - No validation, any string accepted
5. **website** - No validation, any string accepted
6. **dates** - Must be ISO 8601 format if provided

## Synchronization

All contacts created via this API automatically sync to:
- Outlook desktop/web
- Outlook mobile apps (iOS/Android)
- Connected mobile devices (via ActiveSync/Exchange)

Synchronization typically occurs within 1-5 minutes.
