# CRM Command Examples

## Complete Workflow Example

### Scenario: New Customer Onboarding

**Step 1: Create Company**

```
/crm New customer onboarding:

Company: TechInnovate GmbH
Address: Friedrichstraße 95, 10117 Berlin, Germany
Industry: Software Development
Website: www.techinnovate.de
LinkedIn: https://linkedin.com/company/techinnovate
Company Size: 20-50 employees
Annual Revenue: €2.5M
Notes: Fast-growing startup, focused on AI/ML solutions
Tags: startup, ai-company, berlin, potential-partner
```

**Step 2: Add Primary Contact**

```
/crm Primary contact at TechInnovate:

Name: Dr. Anna Schneider
Email: anna.schneider@techinnovate.de
Phone: +49 30 98765432
Mobile: +49 171 1234567
LinkedIn: https://linkedin.com/in/anna-schneider-ai
Job Title: CEO & Founder
Department: Management
Notes: PhD in Computer Science, previously worked at Google. Very interested in our consulting services.
Tags: decision-maker, technical-background, founder
```

**Step 3: Add Technical Contact**

```
/crm Technical contact at TechInnovate:

Name: Michael Weber
Email: m.weber@techinnovate.de
Phone: +49 30 98765433
Job Title: CTO
Department: Engineering
Company: TechInnovate GmbH
Notes: Will be involved in technical evaluation
Tags: technical-evaluator
```

**Step 4: Create Sales Opportunity**

```
/crm New sales opportunity:

Title: "TechInnovate - Enterprise Consulting Package"
Value: €85,000
Probability: 45%
Status: open
Expected Close Date: 2025-03-31
Contact: Dr. Anna Schneider
Company: TechInnovate GmbH
Description: 6-month consulting engagement for AI strategy and implementation. Includes team training, architecture review, and deployment support.
Source: Referral from existing customer (DataTech AG)
Competitors: McKinsey Digital, BCG Digital Ventures
Next Steps:
- Schedule discovery workshop (week of 2025-11-11)
- Prepare custom proposal
- Arrange reference calls with similar customers
Tags: consulting, ai, high-value, q1-2026
```

**Step 5: Log Initial Meeting**

```
/crm Initial meeting today with TechInnovate:

Type: meeting
Date: 2025-11-02 14:00
Attendees: Dr. Anna Schneider (CEO), Michael Weber (CTO)
Company: TechInnovate GmbH
Opportunity: Enterprise Consulting Package

Discussion Points:
- Current AI infrastructure and challenges
- Team composition and skill gaps
- Timeline: Want to start January 2026
- Budget: €80-100k approved for Q1
- Decision process: CEO and CTO jointly, need board approval for >€50k
- Competition: Also talking to McKinsey but prefer specialized boutique firm

Action Items:
- [ ] Send proposal by 2025-11-08
- [ ] Arrange reference calls (2 customers in similar industry)
- [ ] Schedule technical deep-dive with CTO
- [ ] Prepare ROI analysis

Next Meeting: 2025-11-15 at 10:00 - Proposal presentation

Metadata: duration: 90min, location: their office, sentiment: very positive
```

**Step 6: Update Opportunity After Proposal**

```
/crm Update Enterprise Consulting Package opportunity:
- Probability: 65%
- Status: in_progress
- Notes: Proposal sent and well-received. Anna mentioned budget might increase to €95k if we can add team training modules. Board meeting scheduled for 2025-11-20.
```

**Step 7: Log Follow-up Call**

```
/crm Call with Dr. Anna Schneider on 2025-11-18:

Quick check-in before board meeting. She's confident about approval. Mentioned competitor (McKinsey) quoted €150k which makes our proposal very attractive. Asked if we can start pilot phase in December - said yes.

Action: Prepare amendment for December pilot start (€10k additional)
Tags: positive-signal, competitor-intel
```

## Quick Examples

### Creating Records

**Simple Company:**
```
/crm Add company: FastGrow AG, Munich, E-Commerce industry
```

**Simple Contact:**
```
/crm New contact: Peter Müller, p.mueller@example.com, Sales Manager at FastGrow AG
```

**Quick Opportunity:**
```
/crm Opportunity: "FastGrow - Marketing Automation" €35k, 50% probability, contact Peter Müller
```

### Searching

**Find Companies:**
```
/crm Find all companies in Berlin
```

```
/crm Show companies in Software Development industry
```

```
/crm List companies with revenue > €5M
```

**Find Contacts:**
```
/crm All contacts at FastGrow AG
```

```
/crm Find contact with email p.mueller@example.com
```

```
/crm Show all CTOs in our database
```

**Find Opportunities:**
```
/crm Open opportunities over €50k
```

```
/crm All opportunities closing this quarter
```

```
/crm Opportunities with probability > 70%
```

**Activity History:**
```
/crm Recent activities with FastGrow AG
```

```
/crm All meetings in the last 30 days
```

```
/crm Events related to Marketing Automation opportunity
```

### Updating Records

**Update Company:**
```
/crm Update FastGrow AG: new website www.fastgrow-new.com, revenue €8M
```

**Update Contact:**
```
/crm Peter Müller promoted to VP Sales
```

**Update Opportunity:**
```
/crm Marketing Automation deal: probability 85%, expected close 2025-11-30
```

### Analytics

**Pipeline Analysis:**
```
/crm Total value of all open opportunities
```

```
/crm Average deal size by industry
```

```
/crm Conversion rate for opportunities created in Q4
```

**Activity Reports:**
```
/crm How many customer meetings this month?
```

```
/crm Most active contacts (by event count)
```

**Revenue Forecasting:**
```
/crm Weighted pipeline value (probability × value) for Q1 2026
```

```
/crm Expected revenue from deals closing this quarter
```

## Advanced Examples

### Bulk Import

```
/crm Import these contacts:

1. Sarah Johnson, sarah@techcorp.de, CTO, TechCorp Berlin
2. Frank Schmidt, f.schmidt@innovate.de, CEO, InnovateLabs Munich
3. Lisa Weber, lisa.w@digital.com, Product Manager, Digital Solutions Hamburg
4. Thomas Klein, t.klein@future.de, Sales Director, FutureTech Stuttgart

Tag all as: webinar-attendees, q4-2025
```

### Complex Queries

```
/crm Advanced search:
- Companies in Software or Technology industry
- Located in Berlin or Munich
- Revenue between €1M and €10M
- With at least one open opportunity
- Order by total opportunity value
```

### Workflow Automation

```
/crm When opportunity reaches 75% probability:
1. Create follow-up task for next week
2. Tag as "hot-lead"
3. Notify: Add to weekly pipeline review

Apply to: All opportunities > €50k
```

### Data Quality

```
/crm Find duplicate companies (by name similarity)
```

```
/crm Show contacts without email addresses
```

```
/crm List opportunities without next steps defined
```

## Templates

### New Customer Template

```
/crm New customer: [COMPANY NAME]
Address: [STREET], [POSTAL CODE] [CITY], [COUNTRY]
Industry: [INDUSTRY]
Website: [URL]
Size: [EMPLOYEE RANGE]
Revenue: €[AMOUNT]

Primary Contact: [NAME]
Email: [EMAIL]
Phone: [PHONE]
Title: [JOB TITLE]

Initial Opportunity: "[DEAL NAME]"
Value: €[AMOUNT]
Description: [BRIEF DESCRIPTION]
Next Steps: [ACTION ITEMS]
```

### Meeting Notes Template

```
/crm Meeting on [DATE] with [CONTACT] at [COMPANY]:

Agenda:
- [TOPIC 1]
- [TOPIC 2]
- [TOPIC 3]

Key Insights:
- [INSIGHT 1]
- [INSIGHT 2]

Decisions:
- [DECISION 1]
- [DECISION 2]

Action Items:
- [ ] [ACTION 1] - Due: [DATE]
- [ ] [ACTION 2] - Due: [DATE]

Next Meeting: [DATE] at [TIME]
```

### Opportunity Update Template

```
/crm Update [OPPORTUNITY NAME]:
Probability: [%]
Status: [open/in_progress/won/lost]
Next Steps:
- [STEP 1]
- [STEP 2]
Notes: [LATEST DEVELOPMENTS]
Expected Close: [DATE]
```

## Pro Tips

1. **Use consistent naming**: Keep company and contact names consistent for easy searching
2. **Tag liberally**: Tags make filtering and analysis much easier
3. **Link everything**: Always connect persons to companies, opportunities to both
4. **Log immediately**: Record activities right after they happen
5. **Update probabilities**: Keep opportunity probabilities current for accurate forecasting
6. **Use metadata**: Store structured data in JSON for advanced analysis
7. **Review regularly**: Weekly pipeline reviews keep data fresh

## Common Workflows

### Weekly Pipeline Review
```
/crm Show all opportunities with:
- Status: open or in_progress
- Probability > 30%
- Expected close in next 90 days
Order by: probability DESC, value DESC
```

### Monthly Activity Report
```
/crm This month's activities:
- Total meetings
- Total calls
- Total emails sent
- By company (top 10)
- By person (top 10)
```

### Quarterly Business Review
```
/crm Q4 2025 summary:
- New companies added
- New opportunities created
- Opportunities won (count and total value)
- Opportunities lost (count and reasons)
- Pipeline value at quarter end
- Top 3 industries by opportunity count
```
