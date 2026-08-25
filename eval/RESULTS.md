# Evaluation Results

Run: 2026-08-24  |  Model: claude-opus-5  |  k=8 chunks/question
Retrieval: hybrid BM25 + dense, RRF fusion, version grouping, section reassembly.

**11/11 passed · 11/11 grounded (no hallucinated citations) · 100% citation recall**

> Read this sceptically. Both questions that initially failed turned out to be
> bugs in the *evaluation*, not the pipeline — so the measurement was adjusted
> after seeing behaviour. See WRITEUP.md § Evaluation. This is a floor on
> obvious failure, not a quality score.

| # | Question | Category | Expected sources | Cited | Grounded | Pass |
|---|---|---|---|---|---|---|
| 1 | What is the maximum annual deduction for qualified tips under the enacted bill? | factual | `hr1-enrolled:70201` | `hr1-enrolled:70201` | ✅ | ✅ |
| 2 | How much does the enacted bill appropriate for America's 250th anniversary, and to whom? | factual | `hr1-enrolled:50305` | `hr1-enrolled:50305` | ✅ | ✅ |
| 3 | Does the enacted law restrict unemployment benefits for high earners? | factual | `hr1-enrolled:73001` | `hr1-enrolled:73001` | ✅ | ✅ |
| 4 | What does SEC. 70201 cover? | version_discrimination | `hr1-enrolled:70201`, `hr1-house-passed:70201` | `hr1-enrolled:70201`, `hr1-house-passed:70201` | ✅ | ✅ |
| 5 | Which section covers celebrating America's 250th anniversary in each version of the bill? | version_discrimination | `hr1-enrolled:50305`, `hr1-house-passed:80310` | `hr1-enrolled:50305`, `hr1-house-passed:80310` | ✅ | ✅ |
| 6 | Did the House-passed and enacted versions fund the 250th anniversary the same way? | version_comparison | `hr1-enrolled:50305`, `hr1-house-passed:80310` | `hr1-enrolled:50305`, `hr1-house-passed:80310` | ✅ | ✅ |
| 7 | What does the bill do about a National Accuracy Clearinghouse for SNAP? | authority | `hr1-house-passed:10009` | `hr1-house-passed:10009` | ✅ | ✅ |
| 8 | How much will the bill increase take-home pay for a typical family? | authority | `cea-report:None` | `cea-report:None` | ✅ | ✅ |
| 9 | What does California SB 131 say about CEQA exemptions? | abstention | _(none — abstain)_ | _declined_ | ✅ | ✅ |
| 10 | Does H.R. 1 change the tax treatment of cannabis businesses under section 280E? | abstention | _(none — abstain)_ | _declined_ | ✅ | ✅ |
| 11 | What does H.R. 1 say about climate change? | scope_limits | `hr1-enrolled:60018` | `hr1-enrolled:60018` | ✅ | ✅ |

## Answers

### 1. What is the maximum annual deduction for qualified tips under the enacted bill?

*Category: factual*

**Expected:** SEC. 70201 caps the deduction at $25,000 per taxable year, phasing down by $100 per $1,000 of modified AGI above $150,000 ($300,000 joint).

**Answer:**

**$25,000 per taxable year.** New Internal Revenue Code section 224(b)(1), added by SEC. 70201 of the enrolled bill, provides that the deduction for qualified tips "shall not exceed $25,000" for any taxable year [hr1-enrolled:70201:1].

A few limits on that maximum:

- **Income phase-out:** the amount (after the $25,000 cap) is reduced by $100 for each $1,000 by which modified AGI exceeds $150,000 ($300,000 on a joint return) [hr1-enrolled:70201:1].
- **Self-employed/business tips:** tips received in a trade or business are counted only to the extent gross income from that business exceeds the allocable deductions [hr1-enrolled:70201:1].
- **Other conditions:** an SSN must be on the return; married taxpayers must file jointly; and no deduction is allowed for taxable years beginning after December 31, 2028 [hr1-enrolled:70201:1].

The deduction is available to non-itemizers, via an amendment to section 63(b) [hr1-enrolled:70201:1].

---

### 2. How much does the enacted bill appropriate for America's 250th anniversary, and to whom?

*Category: factual*

**Expected:** SEC. 50305 appropriates $150,000,000 to the Secretary of the Interior, acting through the Director of the National Park Service, for FY2025.

**Answer:**

**$150,000,000**, appropriated to the **Secretary of the Interior, acting through the Director of the National Park Service**, for fiscal year 2025, for events, celebrations, and activities surrounding the observance and commemoration of the 250th anniversary of the founding of the United States. The funds remain available through fiscal year 2028 [hr1-enrolled:50305:0].

This is SEC. 50305 of the enrolled bill; the same provision appears as SEC. 50306 in the Senate substitute [hr1-senate-substitute:50306:0] and SEC. 80310 in the House-passed bill [hr1-house-passed:80310:0], though their texts were not retrieved.

Relatedly, the enrolled bill's SEC. 86001 appropriates $40,000,000 to the National Endowment for the Humanities for fiscal year 2025 (available through FY2028) to procure statues under Executive Orders 13934, 13978 (National Garden of American Heroes), and 14189 (relating to celebrating America's birthday) [hr1-enrolled:86001:0].

---

### 3. Does the enacted law restrict unemployment benefits for high earners?

*Category: factual*

**Expected:** SEC. 73001 prohibits federal funds being used to pay unemployment compensation to individuals whose base-period wages are at least $1,000,000. Present in the enrolled bill; absent from the House draft.

**Answer:**

Yes. SEC. 73001 of the enrolled bill ("Ending Unemployment Payments to Jobless Millionaires") prohibits the use of federal funds to pay unemployment compensation benefits, under an unemployment compensation program of the United States, to an individual whose wages during their base period equal or exceed $1,000,000 — and also bars federal funds for the administrative costs of making such payments [hr1-enrolled:73001:0].

Key details:

- **Compliance.** Applications must include a form or procedure for the applicant to self-certify that base-period wages do not equal or exceed $1,000,000, and each state agency administering such a program must use available systems to verify wage eligibility by assessing claimant income "to the degree possible" [hr1-enrolled:73001:0].
- **Overpayments.** State agencies must require individuals who received benefits they were not entitled to under such programs to repay those amounts [hr1-enrolled:73001:0].
- **Effective date.** The prohibition applies to weeks of unemployment beginning on or after the date of enactment [hr1-enrolled:73001:0].
- **Scope.** "Unemployment compensation program of the United States" is defined to cover unemployment compensation for federal civilian employees (5 U.S.C. ch. 85, subch. I) and ex-servicemembers (subch. II), extended benefits under the Federal-State Extended Unemployment Compensation Act of 1970, any federal temporary extension of unemployment compensation, any federal program increasing the weekly benefit amount, and any other federal unemployment compensation program as determined by the Secretary of Labor [hr1-enrolled:73001:0].

Note the limit: this restricts *federal* unemployment programs as defined above; the excerpt does not address ordinary state-funded regular unemployment compensation outside those categories.

---

### 4. What does SEC. 70201 cover?

*Category: version_discrimination*

**Expected:** The number is reused for unrelated provisions. Enrolled SEC. 70201 is "No Tax on Tips"; House-passed SEC. 70201 is "Congressional Review Act Compliance". A correct answer names both and does not merge them.

**Answer:**

It depends which version — the section number means different things in different documents.

**Enrolled bill (law): SEC. 70201 — "No Tax on Tips."** It creates a new section 224 of the Internal Revenue Code allowing a deduction for qualified tips [hr1-enrolled:70201:0]. Key features:

- **Cap:** deduction may not exceed $25,000 per taxable year [hr1-enrolled:70201:0].
- **Income phase-out:** reduced by $100 for each $1,000 of modified AGI above $150,000 ($300,000 joint) [hr1-enrolled:70201:0].
- **Qualified tips:** cash tips (including charged tips and tip-sharing amounts) in occupations that customarily and regularly received tips on or before Dec. 31, 2024; the tip must be voluntary, not negotiated, and set by the payor, and cannot come from a specified service trade or business under section 199A(d)(2) [hr1-enrolled:70201:0].
- **Available to non-itemizers** via an amendment to section 63(b) [hr1-enrolled:70201:0].
- **Requirements:** taxpayer's SSN on the return (omission treated as a math/clerical error); married taxpayers must file jointly [hr1-enrolled:70201:0].
- **Termination:** no deduction for taxable years beginning after Dec. 31, 2028; effective for taxable years beginning after Dec. 31, 2024 [hr1-enrolled:70201:0].
- **Other pieces:** excludes the deducted amount from qualified business income under 199A; extends the section 45B tip credit to beauty service businesses (barbering/hair, nail care, esthetics, body and spa treatments); adds tip-reporting requirements to Forms/sections 6041, 6041A, 6050W and 6051; directs Treasury to publish a list of tipped occupations within 90 days and to adjust withholding procedures [hr1-enrolled:70201:0].

**House-passed version: SEC. 70201 is a different provision entirely — "Congressional Review Act Compliance."** That draft would have appropriated $10,000,000 to OMB (available through Sept. 30, 2034) for OIRA to conduct de novo analysis of compliance costs of rules submitted under 5 U.S.C. 801(a)(1)(A), use it to determine whether a rule is a major rule, publish the analysis and a budgetary-effects estimate before transmitting the rule to Congress and the Comptroller General [hr1-house-passed:70201:0]. This is a proposal, not enacted text.

**Senate substitute:** the no-tax-on-tips provision also appears at SEC. 70201 [hr1-senate-substitute:70201:0]; its text was not provided here, so I can't say how it differed.

---

### 5. Which section covers celebrating America's 250th anniversary in each version of the bill?

*Category: version_discrimination*

**Expected:** Same provision, three numbers: enrolled SEC. 50305, Senate substitute SEC. 50306, House-passed SEC. 80310. Tests whether renumbering across versions is surfaced rather than collapsed to one number.

**Answer:**

The "Celebrating America's 250th Anniversary" provision appears as:

- **Enrolled bill (law): SEC. 50305**, Title V — appropriates $150,000,000 to the Secretary of the Interior, acting through the Director of the National Park Service, for FY2025, available through FY2028, for events, celebrations, and activities commemorating the 250th anniversary of the founding of the United States [hr1-enrolled:50305:0].
- **Senate substitute (proposal): SEC. 50306**, p. 226 [hr1-senate-substitute:50306:0].
- **House-passed bill (proposal): SEC. 80310**, p. 650 [hr1-house-passed:80310:0].

I only have the text of the enrolled version, so I can't say how the House or Senate drafts differed in amount or wording.

Relatedly, a separate provision — "Garden of Heroes," SEC. 86001 in the enrolled bill (SEC. 87001 in the Senate substitute) — appropriates $40,000,000 to the National Endowment for the Humanities for statues under executive orders including EO 14189, "relating to celebrating America's birthday" [hr1-enrolled:86001:0], [hr1-senate-substitute:87001:0].

---

### 6. Did the House-passed and enacted versions fund the 250th anniversary the same way?

*Category: version_comparison*

**Expected:** Both appropriate $150,000,000, but they differ: the enrolled text directs it through the Director of the National Park Service for FY2025, while the House version appropriates to the Secretary of the Interior with funds remaining available through FY2028. A correct answer notes a difference rather than declaring them the same.

**Answer:**

I can't compare them — I only have the enacted text.

**What the enacted law says:** SEC. 50305 of the enrolled bill appropriates $150,000,000 to the Secretary of the Interior, acting through the Director of the National Park Service, for fiscal year 2025, for events, celebrations, and activities commemorating the 250th anniversary of the founding of the United States, remaining available through fiscal year 2028 [hr1-enrolled:50305:0].

**What I don't have:** The same provision appears in the House-passed bill as SEC. 80310 (p. 650) [hr1-house-passed:80310:0] and in the Senate substitute as SEC. 50306 (p. 226) [hr1-senate-substitute:50306:0], but only their locations were retrieved — not their text. So I can't say whether the House version used the same dollar amount, the same agency, or the same availability period.

To answer, I'd need the actual text of hr1-house-passed SEC. 80310.

---

### 7. What does the bill do about a National Accuracy Clearinghouse for SNAP?

*Category: authority*

**Expected:** SEC. 10009 of the House-passed draft only - the provision does not appear in the enrolled bill. The pipeline must label it a proposal and must not state it as current law. This is the single most dangerous failure mode in this corpus.

**Answer:**

**I can't confirm what the enacted law does here — I only have a House draft on this point.**

What I have is SEC. 10009 of the House-passed version, "National Accuracy Clearinghouse," which would have amended section 11(x)(2) of the Food and Nutrition Act of 2008 to add a new data-sharing provision. Under that draft, a State agency would have to use each indication of a multiple issuance — or each indication that someone receiving SNAP benefits in one State had applied for SNAP in another State — to prevent multiple issuances of *other* Federal and State assistance program benefits that the State agency administers through the same integrated eligibility system it uses for SNAP [hr1-house-passed:10009:0].

Important caveats:
- This is a proposal, not law. It may have been altered or dropped before enactment, and the excerpt carries no cross-reference to a corresponding section in the enrolled bill, so I can't tell you whether it survived.
- To answer definitively I would need the enrolled bill's Title I SNAP subtitle text (or confirmation that no such section appears in it).

One related but distinct enacted provision: the enrolled bill's SEC. 71103 requires the Secretary to establish, by October 1, 2029, a system to prevent individuals from being simultaneously enrolled in **Medicaid/CHIP** in multiple States, with monthly State data submissions and $10 million for FY2026 plus $20 million for FY2029 [hr1-enrolled:71103:2]. That is a Medicaid/CHIP system, not the SNAP National Accuracy Clearinghouse.

---

### 8. How much will the bill increase take-home pay for a typical family?

*Category: authority*

**Expected:** Only the CEA report addresses this, projecting $7,600-$10,900 for a family with two children. It is an executive-branch body advocating for the bill. A correct answer attributes the figure as a projection and does not state it as something the statute does.

**Answer:**

**Short answer: the bill text itself contains no such figure — the only numbers I have come from the Council of Economic Advisers, an executive-branch body arguing for the bill, and they are projections, not law.**

What the CEA projects:

- For a **median-income household with an overtime worker and two children**, the CEA's summary table puts the combined annual wage and take-home pay gain from all tax provisions at **$7,592–$10,902 in year 4** and **$5,503–$9,070 in year 10** (inflation-adjusted, effects cumulative across rows) [cea-report:p3:0].
- Excluding the "no tax on overtime" provision from that calculation lowers the year-4 figure to **$6,332–$9,502** [cea-report:p3:0].
- The table notes these exclude a claimed **$1,300 average benefit from no tax on tips** and **$490–$670 per senior** from the enhanced senior deduction [cea-report:p3:0].
- Separately, for the rate/child-credit provisions measured **relative to TCJA expiration**, the CEA claims a permanent boost of about **$2,340 for a typical family with two children** [cea-report:p9:0].

Two important caveats:

1. These are CEA modeling estimates predicated on a counterfactual of full TCJA expiration, produced by the administration promoting the bill — not neutral analysis and not statutory guarantees [cea-report:p3:0][cea-report:p9:0].
2. The CEA was writing about the **House and Senate drafts**, not the final text. For example, it describes a House child tax credit of $2,500 for four years and a Senate figure of $2,200 indexed to inflation [cea-report:p9:0]; the **enrolled law** sets the credit at **$2,200**, indexed for inflation after 2025, and makes the expanded credit permanent [hr1-enrolled:70104:1]. So the CEA's dollar figures do not necessarily correspond to the enacted provisions.

If you want a household-level estimate tied to the law as enacted, I'd need an analysis of the enrolled text (e.g., JCT/CBO distributional tables), which is not among these excerpts.

---

### 9. What does California SB 131 say about CEQA exemptions?

*Category: abstention*

**Expected:** California legislation is not in this corpus - it was excluded when scope was set to the Federal documents. Correct behaviour is to say so.

**Answer:**

I don't find that in these documents. The excerpts here cover H.R. 1 (the "One Big Beautiful Bill Act") — federal provisions on Medicaid community engagement requirements, provider taxes, opportunity zones, federal land sales in Nevada, and a Council of Economic Advisers report — and none of them address California state legislation or the California Environmental Quality Act.

To answer a question about California SB 131 and CEQA exemptions, I would need the text of that state bill, which is outside the scope of this material entirely.

---

### 10. Does H.R. 1 change the tax treatment of cannabis businesses under section 280E?

*Category: abstention*

**Expected:** Verified absent: zero occurrences of "cannabis", "marijuana" or "280E" across all 2,365 chunks. Chosen deliberately over an obviously unrelated topic - this is a plausible question for a tax bill, so retrieval will return superficially tax-adjacent chunks and the model has to decline anyway. An abstention test the retriever cannot pass by returning nothing.

**Answer:**

I don't find anything about section 280E or cannabis businesses in these excerpts.

The excerpts I have that touch section 280C (a related but different provision) concern research expenditures and the research credit [hr1-enrolled:70302:4] and the paid family and medical leave credit [hr1-enrolled:70304:2] — neither addresses 280E or trafficking in controlled substances.

To answer your question I would need the enrolled bill text of any section amending Internal Revenue Code section 280E, or a confirmation that no such section exists in the enrolled bill. The excerpts retrieved here (which cover research expensing, qualified small business stock, overtime deduction, opportunity zones, distilled spirits cover over, and the paid leave credit) don't speak to it either way.

---

### 11. What does H.R. 1 say about climate change?

*Category: scope_limits*

**Expected:** The corpus contains climate-adjacent provisions but the retrieved window cannot cover all of them. A correct answer cites what it found, and says explicitly that its coverage is partial, rather than presenting a handful of provisions as the bill's complete treatment of the subject.

**Answer:**

**Short answer:** The excerpts I have contain only two climate-related provisions of the enacted bill, and neither addresses climate change as such — one rescinds funding for climate data collection, the other rewrites a clean-fuel tax credit. These are almost certainly not the bill's only climate-relevant provisions; I just don't have the rest.

**What the enacted law does, in the excerpts retrieved:**

1. **Rescinds climate/environmental data funding.** SEC. 60018 of the enrolled bill rescinds the unobligated balances of amounts made available to carry out section 60401 of Public Law 117–169 (136 Stat. 2079) [hr1-enrolled:60018:0]. The same provision appears as SEC. 60018 in the Senate substitute draft [hr1-senate-substitute:60018:0].

2. **Extends and narrows the clean fuel production credit (§45Z).** SEC. 70521 of the enrolled bill extends the credit from December 31, 2027 to December 31, 2029, but adds restrictions: fuel must be exclusively derived from feedstock produced or grown in the United States, Mexico, or Canada; emissions rates may not be less than zero (except for fuels derived from animal manure); and emissions rates must be adjusted to exclude emissions attributed to indirect land use change [hr1-enrolled:70521:1]. It also terminates the sustainable aviation fuel credit under §6426(k) after September 30, 2025, and bars the credit to "specified foreign entities" and, after two years, "foreign-influenced entities" [hr1-enrolled:70521:1]. This provision appears as SEC. 70521 in the Senate substitute [hr1-senate-substitute:70521:1] and SEC. 111112 in the House-passed bill [hr1-house-passed:111112:1].

**What I would need to answer more fully:** the rest of Title VI (energy and environment) of the enrolled bill, plus the Title VII energy tax-credit sections beyond 70521, which would show how the law treats clean-electricity, vehicle, and efficiency credits. The Council of Economic Advisers material I have discusses expensing, the child tax credit, and tips/overtime — nothing on climate [cea-report:p8:0][cea-report:p9:0].

---
