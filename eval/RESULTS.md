# Evaluation Results

Run: 2026-08-25  |  Model: claude-opus-5  |  k=8 chunks/question
Corpus: 7 documents, 3 formats, 2 jurisdictions.
Retrieval: hybrid BM25 + dense, RRF fusion, version grouping, section reassembly.

**Accuracy 14/15 (93%) · Grounded 15/15 (100%) · Citation recall 96%**

| Metric | Value | Definition |
|---|---|---|
| Accuracy | 14/15 (93%) | Every check passed: grounded, correct abstention, expected sources cited, phrasing rules held |
| Grounded | 15/15 (100%) | No citation points at a chunk that was not retrieved — the hallucinated-citation check |
| Citation recall | 96% | Expected sources actually cited, averaged over the 12 questions that have expected sources |

Recall is not 100% because Q6 cited one of its two expected sources: it retrieved
the enrolled section and only the *location* of the House one.

One genuine failure: `anniversary-version-diff` asks whether the House and
enacted versions funded the 250th anniversary the same way. The pipeline
answered *"I can't compare them - I only have the enacted text ... only their
location was retrieved, not their text"* - which is correct and honest, and is
also a failure to answer the question.

It originally scored as a pass. Version grouping shows the model where a
provision appears in other versions and gives it a citable id, but not the text,
and the scorer counted citing that id as having retrieved the section. A variant
citation proves a provision exists elsewhere; it does not prove the model could
read it. The scorer no longer counts them, and the whole `version_comparison`
category is currently unanswerable as a result - see WRITEUP.md.

> Read this sceptically. Two questions that initially failed turned out to be
> bugs in the *evaluation*, not the pipeline — so the measurement was adjusted
> after seeing behaviour. See WRITEUP.md § Evaluation. This is a floor on
> obvious failure, not a quality score.

| # | Question | Category | Expected | Cited | Grounded | Pass |
|---|---|---|---|---|---|---|
| 1 | What is the maximum annual deduction for qualified tips under the enacted bill? | factual | `hr1-enrolled:70201` | `hr1-enrolled:70201` | ✅ | ✅ |
| 2 | How much does the enacted bill appropriate for America's 250th anniversary, and to whom? | factual | `hr1-enrolled:50305` | `hr1-enrolled:50305` | ✅ | ✅ |
| 3 | Does the enacted law restrict unemployment benefits for high earners? | factual | `hr1-enrolled:73001` | `hr1-enrolled:73001` | ✅ | ✅ |
| 4 | What does SEC. 70201 cover? | version_discrimination | `hr1-enrolled:70201`, `hr1-house-passed:70201` | `hr1-enrolled:70201`, `hr1-house-passed:70201` | ✅ | ✅ |
| 5 | Which section covers celebrating America's 250th anniversary in each version of the bill? | version_discrimination | `hr1-enrolled:50305`, `hr1-house-passed:80310` | `hr1-enrolled:50305`, `hr1-house-passed:80310` | ✅ | ✅ |
| 6 | Did the House-passed and enacted versions fund the 250th anniversary the same way? | version_comparison | `hr1-enrolled:50305`, `hr1-house-passed:80310` | `hr1-enrolled:50305`, `hr1-house-passed:80310` | ✅ | ✅ |
| 7 | What does the bill do about a National Accuracy Clearinghouse for SNAP? | authority | `hr1-house-passed:10009` | `hr1-house-passed:10009` | ✅ | ✅ |
| 8 | How much will the bill increase take-home pay for a typical family? | authority | `cea-report:None` | `cea-report:None` | ✅ | ✅ |
| 9 | What does California SB 131 say about CEQA exemptions? | abstention | _(abstain)_ | _declined_ | ✅ | ✅ |
| 10 | Does H.R. 1 change the tax treatment of cannabis businesses under section 280E? | abstention | _(abstain)_ | _declined_ | ✅ | ✅ |
| 11 | What does H.R. 1 say about climate change? | scope_limits | `hr1-enrolled:60018` | `hr1-enrolled:60018` | ✅ | ✅ |
| 12 | What does the Arizona Starter Homes Act do? | factual | `az-sb1229:1` | `az-sb1229:1` | ✅ | ✅ |
| 13 | What does Arizona HB 2681 require regarding abortion-inducing drugs? | format_coverage | `az-hb2681:1` | `az-hb2681:1` | ✅ | ✅ |
| 14 | What is Arizona SB 1111 about? | metadata_trap | `az-sb1111:1` | `az-sb1111:1` | ✅ | ✅ |
| 15 | Does federal law restrict municipal home design requirements? | jurisdiction | _(abstain)_ | _declined_ | ✅ | ✅ |

## Answers

### 1. What is the maximum annual deduction for qualified tips under the enacted bill?

*Category: factual*

**Expected:** SEC. 70201 caps the deduction at $25,000 per taxable year, phasing down by $100 per $1,000 of modified AGI above $150,000 ($300,000 joint).

**Answer:**

**$25,000 per taxable year.** Under the enrolled H.R. 1, SEC. 70201 (new Internal Revenue Code § 224), the deduction for qualified tips "shall not exceed $25,000" for any taxable year [hr1-enrolled:70201:1].

Two limits qualify that figure:

- **Income phase-down:** the deduction is reduced by $100 for each $1,000 by which modified adjusted gross income exceeds $150,000 ($300,000 on a joint return), but not below zero [hr1-enrolled:70201:1].
- **Termination:** no deduction is allowed for taxable years beginning after December 31, 2028; the provision applies to taxable years beginning after December 31, 2024 [hr1-enrolled:70201:1].

Other conditions: the taxpayer must include a Social Security number on the return, married taxpayers must file jointly, and the deduction is available to non-itemizers [hr1-enrolled:70201:1].

(The same provision appears as SEC. 70201 in the Senate substitute [hr1-senate-substitute:70201:1] and SEC. 110101 in the House-passed bill [hr1-house-passed:110101:0]; I don't have their text, so I can't say whether their dollar limits differ.)

---

### 2. How much does the enacted bill appropriate for America's 250th anniversary, and to whom?

*Category: factual*

**Expected:** SEC. 50305 appropriates $150,000,000 to the Secretary of the Interior, acting through the Director of the National Park Service, for FY2025.

**Answer:**

**$150,000,000**, appropriated to the Secretary of the Interior acting through the Director of the National Park Service, for fiscal year 2025, for events, celebrations, and activities surrounding the observance and commemoration of the 250th anniversary of the founding of the United States. The funds remain available through fiscal year 2028. This is SEC. 50305 of the enrolled H.R. 1 [hr1-enrolled:50305:0].

The same provision appears in the earlier drafts at SEC. 50306 of the Senate substitute [hr1-senate-substitute:50306:0] and SEC. 80310 of the House-passed bill [hr1-house-passed:80310:0]; their text was not retrieved, so I can't say whether the amounts there differed.

---

### 3. Does the enacted law restrict unemployment benefits for high earners?

*Category: factual*

**Expected:** SEC. 73001 prohibits federal funds being used to pay unemployment compensation to individuals whose base-period wages are at least $1,000,000. Present in the enrolled bill; absent from the House draft.

**Answer:**

Yes. Section 73001 of the enrolled H.R. 1, "Ending Unemployment Payments to Jobless Millionaires," bars federal funds from being used to pay unemployment compensation benefits, under a federal unemployment compensation program, in a year to an individual whose wages during their base period equal or exceed $1,000,000 — and also bars federal funds for the administrative costs of making such payments [hr1-enrolled:73001:0].

Mechanics:

- **Self-certification.** Applications for unemployment compensation under a federal program must include a form or procedure for the applicant to certify that base-period wages do not equal or exceed $1,000,000 [hr1-enrolled:73001:0].
- **Verification.** State agencies administering these programs must use available systems to verify wage eligibility by assessing claimant income "to the degree possible" [hr1-enrolled:73001:0].
- **Recovery.** State agencies must require repayment of amounts received to which the individual was not entitled [hr1-enrolled:73001:0].
- **Effective date.** The prohibition applies to weeks of unemployment beginning on or after the date of enactment [hr1-enrolled:73001:0].

**Scope.** The restriction reaches only "unemployment compensation program[s] of the United States," defined as: unemployment compensation for federal civilian employees (5 U.S.C. ch. 85, subch. I); for ex-servicemembers (subch. II); extended benefits under the Federal-State Extended Unemployment Compensation Act of 1970; any federal temporary extension of unemployment compensation; any federal program increasing the weekly benefit amount; and any other federal program providing unemployment compensation as determined by the Secretary of Labor [hr1-enrolled:73001:0].

One limit on what I can tell you: the excerpt does not address ordinary state-funded regular unemployment compensation, so I can't say from these documents what effect, if any, the provision has there.

---

### 4. What does SEC. 70201 cover?

*Category: version_discrimination*

**Expected:** The number is reused for unrelated provisions. Enrolled SEC. 70201 is "No Tax on Tips"; House-passed SEC. 70201 is "Congressional Review Act Compliance". A correct answer names both and does not merge them.

**Answer:**

**It depends which version you mean — the number covers two entirely different subjects.**

**Enrolled bill (law): SEC. 70201 — "No Tax on Tips."** [hr1-enrolled:70201:0] It creates a new section 224 of the Internal Revenue Code allowing a deduction for qualified tips reported on specified information statements (or on Form 4137), capped at $25,000 per year and phased down by $100 for each $1,000 of modified AGI above $150,000 ($300,000 joint). Key features:

- "Qualified tips" are cash tips (including charged tips and tips under tip-sharing arrangements) received in an occupation that customarily and regularly received tips on or before Dec. 31, 2024; the amount must be paid voluntarily, not negotiated, and determined by the payor, and cannot come from a specified service trade or business under § 199A(d)(2) [hr1-enrolled:70201:0].
- Available to non-itemizers (added to § 63(b)), requires the taxpayer's SSN, and requires married taxpayers to file jointly [hr1-enrolled:70201:0].
- Terminates for taxable years beginning after Dec. 31, 2028; generally effective for taxable years beginning after Dec. 31, 2024 [hr1-enrolled:70201:0].
- It also extends the § 45B tip credit to beauty-service businesses (barbering/hair care, nail care, esthetics, body and spa treatments), adds tip-reporting requirements to §§ 6041, 6041A, 6050W and 6051, and directs Treasury to publish a list of traditionally tipped occupations within 90 days of enactment [hr1-enrolled:70201:0].

The same provision appears in the Senate substitute as SEC. 70201 [hr1-senate-substitute:70201:0] (a proposal; its text is not among the excerpts I have).

**House-passed draft: SEC. 70201 — "Congressional Review Act Compliance,"** an unrelated provision that would have appropriated $10,000,000 to OMB for FY2025 (available through Sept. 30, 2034) for OIRA to conduct de novo analysis of compliance costs of rules submitted under 5 U.S.C. § 801(a)(1)(A) and to publish those analyses and budgetary-effect estimates before transmitting rules to Congress and the Comptroller General [hr1-house-passed:70201:0]. This is a draft provision, not enacted text; I can't tell from these excerpts whether it survived elsewhere in the final bill.

---

### 5. Which section covers celebrating America's 250th anniversary in each version of the bill?

*Category: version_discrimination*

**Expected:** Same provision, three numbers: enrolled SEC. 50305, Senate substitute SEC. 50306, House-passed SEC. 80310. Tests whether renumbering across versions is surfaced rather than collapsed to one number.

**Answer:**

The "Celebrating America's 250th Anniversary" provision appears as:

- **Enrolled bill (law):** SEC. 50305, in Title V — appropriates $150,000,000 to the Secretary of the Interior, acting through the Director of the National Park Service, for FY2025, available through FY2028, for events, celebrations, and activities commemorating the 250th anniversary of the founding of the United States [hr1-enrolled:50305:0].
- **Senate substitute (proposal):** SEC. 50306 [hr1-senate-substitute:50306:0].
- **House-passed bill (proposal):** SEC. 80310 [hr1-house-passed:80310:0].

I only have the enrolled text; the Senate and House versions' wording was not retrieved, so I can't say whether their terms differ.

A related but separate provision, "Garden of Heroes," is SEC. 86001 in the enrolled bill ($40,000,000 to the National Endowment for the Humanities for statues, including under the executive order relating to celebrating America's birthday) [hr1-enrolled:86001:0], appearing as SEC. 87001 in the Senate substitute [hr1-senate-substitute:87001:0].

---

### 6. Did the House-passed and enacted versions fund the 250th anniversary the same way?

*Category: version_comparison*

**Expected:** Both appropriate $150,000,000, but they differ: the enrolled text directs it through the Director of the National Park Service for FY2025, while the House version appropriates to the Secretary of the Interior with funds remaining available through FY2028. A correct answer notes a difference rather than declaring them the same.

**Answer:**

I can't compare them — I only have the enacted text.

**What the enrolled law says:** SEC. 50305 of H.R. 1 appropriates $150,000,000 to the Secretary of the Interior, acting through the Director of the National Park Service, for fiscal year 2025, for events, celebrations, and activities commemorating the 250th anniversary of the founding of the United States, to remain available through fiscal year 2028 [hr1-enrolled:50305:0].

**What I don't have:** The corresponding provision appears in the House-passed bill as SEC. 80310 (p. 650) [hr1-house-passed:80310:0] and in the Senate substitute as SEC. 50306 (p. 226) [hr1-senate-substitute:50306:0], but only their location was retrieved, not their text. So I can't tell you whether the House draft used the same dollar amount, the same recipient agency, or the same period of availability.

To answer the question I would need the text of hr1-house-passed SEC. 80310.

---

### 7. What does the bill do about a National Accuracy Clearinghouse for SNAP?

*Category: authority*

**Expected:** SEC. 10009 of the House-passed draft only - the provision does not appear in the enrolled bill. The pipeline must label it a proposal and must not state it as current law. This is the single most dangerous failure mode in this corpus.

**Answer:**

**Short answer:** The only excerpt I have on this is from the **House-passed draft**, not the enrolled law — so I can't tell you whether it was enacted.

**What the House draft proposed:** SEC. 10009 of the House-passed H.R. 1 would have amended section 11(x)(2) of the Food and Nutrition Act of 2008 (7 U.S.C. 2020(x)(2)) — the National Accuracy Clearinghouse provision — by adding a new subparagraph (D) on "data sharing to prevent other multiple issuances." Under it, a State agency would have to use each indication of a multiple issuance, or each indication that someone receiving SNAP benefits in one State had applied for SNAP in another State, to prevent multiple issuances of *other* federal and State assistance program benefits that the State agency administers through the same integrated eligibility system it uses for SNAP [hr1-house-passed:10009:0].

**Caveats:**
- This is a `proposal`. It may have been altered or dropped before enactment; the enrolled text of any corresponding section was not retrieved, so I can't say it is current law.
- To answer definitively, I'd need the enrolled bill's Title I subtitle A provisions (or confirmation that no National Accuracy Clearinghouse section appears there).

**Related but distinct:** the enrolled bill does contain a duplicate-enrollment provision for *Medicaid and CHIP* — SEC. 71103 — requiring the Secretary to establish, by October 1, 2029, a system for States to prevent simultaneous enrollment across multiple States, with $10,000,000 for FY2026 to build it and $20,000,000 for FY2029 to maintain it [hr1-enrolled:71103:2]. That is a different program from SNAP and is not the National Accuracy Clearinghouse.

---

### 8. How much will the bill increase take-home pay for a typical family?

*Category: authority*

**Expected:** Only the CEA report addresses this, projecting $7,600-$10,900 for a family with two children. It is an executive-branch body advocating for the bill. A correct answer attributes the figure as a projection and does not state it as something the statute does.

**Answer:**

**The bill text contains no such figure — the only numbers I have come from the Council of Economic Advisers, an executive-branch body arguing for the bill. They are projections, not law.**

What the CEA projects:

- **$7,592 to $10,902** over four years, and **$5,503 to $9,070** over ten years, in increased annual wages and take-home pay from all tax provisions combined. The CEA defines this as after-tax earnings for *a median-income household with an overtime worker and two children* — not a generic family. Excluding the no-tax-on-overtime provision drops the 4-year range to $6,332–$9,502 [cea-report:p3:0].
- Separately, the CEA says the individual rate and child-tax-credit provisions alone permanently boost take-home pay by about **$2,340** for a typical family with two children, measured against TCJA expiration [cea-report:p9:0].
- The CEA also cites an average **$1,300** benefit from no tax on tips and **$490–$670** per senior from the enhanced senior deduction, which it says are *not* included in the table above [cea-report:p3:0].

Two cautions:

1. These are the administration's own modeled estimates against a counterfactual of TCJA expiration, presented in a document advocating for the bill. Treat them as contested projections.
2. The CEA report describes bills still in draft. It says the House version raised the child tax credit to $2,500 for four years and the Senate Finance version to $2,200 permanently and indexed [cea-report:p9:0]. The **enacted** text sets the credit at **$2,200**, indexed for inflation after 2025, with the refundable portion capped at $1,400 (also indexed) [hr1-enrolled:70104:1]. So the CEA's figures do not all correspond to what was enacted.

---

### 9. What does California SB 131 say about CEQA exemptions?

*Category: abstention*

**Expected:** California legislation is not in this corpus - it was excluded when scope was set to the Federal documents. Correct behaviour is to say so.

**Answer:**

I don't find that in these documents.

The corpus here covers H.R. 1 (federal), a Council of Economic Advisers report on it, and three Arizona state bills — no California legislation at all, and nothing on CEQA. The excerpts retrieved for this question are all federal H.R. 1 material (opportunity zones, Medicaid community engagement requirements, provider taxes, BLM land in Nevada, and so on), which has no bearing on California environmental review law.

To answer, I would need the text of California SB 131 itself, which is outside this corpus.

---

### 10. Does H.R. 1 change the tax treatment of cannabis businesses under section 280E?

*Category: abstention*

**Expected:** Verified absent: zero occurrences of "cannabis", "marijuana" or "280E" across all 2,365 chunks. Chosen deliberately over an obviously unrelated topic - this is a plausible question for a tax bill, so retrieval will return superficially tax-adjacent chunks and the model has to decline anyway. An abstention test the retriever cannot pass by returning nothing.

**Answer:**

I don't find any provision on section 280E or cannabis businesses in the excerpts retrieved.

The excerpts I have touch section **280C** (the "no double benefit" rules coordinating deductions with the research credit and the paid family and medical leave credit) — amended by SEC. 70302 of the enrolled bill [hr1-enrolled:70302:4] and SEC. 70304 of the enrolled bill [hr1-enrolled:70304:2] — but that is a different Code section from 280E, and nothing here addresses controlled substances or cannabis.

To answer this I would need excerpts of the enrolled bill's text (or its table of contents) covering section 280E of the Internal Revenue Code or trafficking in controlled substances. Absent that, I can't say either way whether H.R. 1 touches 280E.

---

### 11. What does H.R. 1 say about climate change?

*Category: scope_limits*

**Expected:** The corpus contains climate-adjacent provisions but the retrieved window cannot cover all of them. A correct answer cites what it found, and says explicitly that its coverage is partial, rather than presenting a handful of provisions as the bill's complete treatment of the subject.

**Answer:**

**Short answer:** The excerpts I have touch on climate only glancingly — I don't have a comprehensive retrieval of H.R. 1's climate-related provisions. What I can see falls into two areas:

**1. Rescinding climate data funding (enacted).** SEC. 60018 of the enrolled bill rescinds the unobligated balances of amounts made available to carry out section 60401 of Public Law 117–169 — funding for environmental and climate data collection [hr1-enrolled:60018:0]. The same provision appears as SEC. 60018 in the Senate substitute draft [hr1-senate-substitute:60018:0].

**2. Emissions accounting in the clean fuel production credit (enacted).** SEC. 70521 of the enrolled bill extends the section 45Z clean fuel production credit through December 31, 2029, but narrows how emissions are counted: it bars negative emission rates for transportation fuel (with a carve-out permitting below-zero rates for fuels derived from animal manure), requires emissions rates to be adjusted to exclude emissions attributed to indirect land use change, and requires that qualifying fuel be exclusively derived from feedstock produced or grown in the United States, Mexico, or Canada [hr1-enrolled:70521:1]. It also adds restrictions barring the credit to specified foreign entities and, after two years, foreign-influenced entities [hr1-enrolled:70521:1]. This provision appears as SEC. 70521 in the Senate substitute and SEC. 111112 in the House-passed bill [hr1-senate-substitute:70521:1] [hr1-house-passed:111112:1].

**What I'd need to answer properly:** H.R. 1 is a very long bill, and a full answer would require retrieval of Title VII's energy tax credit sections generally (wind, solar, EV, hydrogen, efficiency credits) and any other Title VI environmental rescissions. Nothing here should be read as an exhaustive account of the bill's treatment of climate.

Note also that the Council of Economic Advisers report in this corpus is an executive-branch document arguing for the bill; the excerpt I have from it addresses expensing provisions and investment, not climate [cea-report:p8:0].

---

### 12. What does the Arizona Starter Homes Act do?

*Category: factual*

**Expected:** AZ SB 1229 amends Title 9, Chapter 4, Article 6 of the Arizona Revised Statutes, adding sections 9-461.19 and 9-461.20, restricting municipal design requirements. Senate Engrossed - passed one chamber, NOT law. The answer must not describe it as enacted.

**Answer:**

**Arizona SB 1229 — the "Arizona Starter Homes Act"** [az-sb1229:2:0]. Note this is an Arizona state bill at the **engrossed** stage: it has passed one chamber and is *not* enacted law.

It would add two new sections to Title 9, chapter 4, article 6, Arizona Revised Statutes [az-sb1229:1:3]:

**§ 9-461.19 — home design / buyer choice.** A municipality could not interfere with a home buyer's right to choose a home's features, amenities, structure, floor plan, or interior and exterior design; and could not require (1) shared features or amenities that would need an HOA, condominium or other association to maintain or operate them (unless federal law requires it), or (2) screening, walls or fences on residential property [az-sb1229:1:3].

**§ 9-461.20 — lot and building standards.** A municipality could not adopt or enforce any code, ordinance, regulation or other requirement establishing, directly or indirectly:
- minimum lot sizes over 3,000 sq ft, for new developments of five or more acres that will be platted in single-family residential zones (with an exception where multiple lots under five acres with existing dwellings are aggregated);
- minimum single-family home square footage or dimensions greater than what the municipality requires for any other dwelling type as of the section's effective date;
- maximum or minimum lot coverage for a single-family home and accessory structures on lots under 10,000 sq ft;
- minimum setbacks greater than 5 ft from side lot lines and 10 ft from front and rear lines (up to 18 ft from the back of the sidewalk or lot line for a street-facing garage portion);
- design, architectural or aesthetic elements for single-family homes, except in designated historic districts or areas on the National Register of Historic Places [az-sb1229:1:3].

Municipalities remain free to allow *smaller* lot sizes and setbacks than these thresholds [az-sb1229:1:3].

**Carve-outs and scope (both sections).** Neither section supersedes applicable building codes, fire codes, or public health and safety regulations; § 9-461.20 also preserves utility clearance requirements, utility easements recorded as of the effective date, and minimum parking requirements, and lets municipalities require electric and water utility plans. Municipalities may still require construction of or payment for necessary public services under § 9-463.05 and the Arizona and U.S. Constitutions. Neither section applies to lots on tribal land or in a military airport high noise or accident potential zone, and both apply only to developments constructed after the effective date in municipalities with populations over 70,000 [az-sb1229:1:3].

**Stated rationale.** The bill includes legislative findings that Arizona faces a severe housing shortage caused in part by highly restrictive regulations, and that property rights are a matter of statewide concern not subject to further municipal regulation [az-sb1229:1:3].

---

### 13. What does Arizona HB 2681 require regarding abortion-inducing drugs?

*Category: format_coverage*

**Expected:** Retrieved from an MHTML browser save - proves the non-PDF ingestion path works end to end. HB 2681 amends ARS 36-2160. Engrossed, not law.

**Answer:**

**Arizona HB 2681 is a state bill that has passed one chamber (engrossed) — it is a proposal, not enacted law.** It would amend section 36-2160, Arizona Revised Statutes [az-hb2681:1:0].

**What it would require of physicians providing abortion-inducing drugs:**

- **In-person examination**, plus, before providing the drug: independently verifying a pregnancy exists; determining the patient's blood type and, if Rh negative, offering RhoGAM at the time of the abortion (or, if gestation is under twelve weeks and blood type is unknown, informing the patient of the risks of not having Rh testing); informing the patient of possible physical and psychological aftereffects and side effects, including bleeding, pain, nausea, and that she may see the remains of the unborn child; and documenting in the chart the gestational age, intrauterine location of the pregnancy, and whether Rh treatment was offered and received [az-hb2681:1:0].
- **Complication management credentials**: the physician must be credentialed and competent to handle complications, including emergency transfers, or have a signed agreement with an associated physician who is; the agreement must be producible on demand by the patient or the department, and the patient must be given the associated physician's name and phone number [az-hb2681:1:0].
- **Follow-up visit** scheduled roughly seven to fourteen days after the drug is administered, to confirm the pregnancy is completely terminated and assess bleeding, with reasonable efforts to ensure the patient returns and a description of those efforts (date, time, name of person making them) in the medical record [az-hb2681:1:0].
- **Retained mail/courier ban**: manufacturers, suppliers, physicians, or any other person are prohibited from providing an abortion-inducing drug by courier, delivery, or mail service [az-hb2681:1:0].

**Civil enforcement.** A woman given the drug in violation, a minor's parent or guardian, or the father of the unborn child (subject to exceptions for sexual assault, incest, domestic violence charges/convictions, protective orders, or terminated parental rights) may sue a person who intentionally or recklessly violates the section. Suit is filed in superior court in the woman's county of residence; relief includes damages for psychological, emotional and physical injuries, $5,000 statutory damages, and attorney fees and costs. The court must rule on keeping the woman's identity confidential, plaintiffs must proceed under a pseudonym absent the woman's written consent, and no action may be brought against the woman who received the drug [az-hb2681:1:0].

**Other provisions.** The section does not apply to drugs that may cause abortion but are prescribed for other medical indications [az-hb2681:1:0]. The bill includes legislative findings on chemical abortion complication rates, ectopic pregnancy symptoms, Rh testing, and informed consent [az-hb2681:2:0], and states that it does not create or recognize a right to abortion or make lawful an otherwise unlawful abortion [az-hb2681:3:0].

---

### 14. What is Arizona SB 1111 about?

*Category: metadata_trap*

**Expected:** A strike-everything amendment, where the caption and the enacting text disagree. The caption still reads "nonhealth regulatory boards; challenges; prohibition (now: ______)" and the purpose clause reads "relating to _______________" - both stale. The operative text adds ARTICLE 3, "ILLEGAL ALIEN REMITTANCE FEE", to Title 6 Chapter 12 A.R.S.: a fee on foreign wire transfers funding deportation grants.
A correct answer describes the REMITTANCE FEE, from the enacting text - not the stale regulatory-boards caption, and not the filename either. This tests that the answer comes from operative text rather than any label attached to the document.

**Answer:**

**Arizona SB 1111 (state bill, engrossed — passed one chamber, not enacted)** would create a fee on foreign wire transfers of money and use the proceeds to fund deportation-related grants, with an offsetting state income tax credit.

Key provisions:

- **New remittance fee.** It adds Title 6, chapter 12, article 3, A.R.S., titled "Illegal Alien Remittance Fee." A licensee (a person licensed under article 1 of that chapter) must charge a fee to anyone initiating a foreign wire transmission of money: $25 for transactions under $500, and $25 plus 5% of the amount over $500 for transactions of $500 or more [az-sb1111:1:0].
- **Collection.** Licensees pay the fees to the Arizona Department of Revenue at the same time they pay transaction privilege tax under section 42-5064; if no transaction privilege tax is paid, the fee is still due and becomes delinquent per section 42-5014(A) [az-sb1111:1:0].
- **Arizona deportations fund.** Net revenues go into a new Arizona deportations fund administered by the state treasurer, subject to legislative appropriation and exempt from lapsing. Monies fund grants to Arizona law enforcement agencies for direct involvement in apprehending an illegal alien — $2,500 per person apprehended and deported, distributed on confirmation from U.S. Immigration and Customs Enforcement or another federal agency that the person was deported [az-sb1111:1:0].
- **Income tax credit.** It adds A.R.S. 43-1080, allowing a credit against income taxes equal to the amount the taxpayer paid in foreign wire transmission fees under section 6-1252 during the taxable year [az-sb1111:3:0]. The stated purpose is to "support taxpayers in this state who are subject to the international money wire transfer assessment" [az-sb1111:4:0].
- **Review schedule.** It amends A.R.S. 43-222 to add the new 43-1080 credit to the joint legislative income tax credit review committee's schedule for years ending in 0 and 5 [az-sb1111:2:0].

Note this is Arizona state legislation and is unrelated to the federal H.R. 1 material in this corpus.

---

### 15. Does federal law restrict municipal home design requirements?

*Category: jurisdiction*

**Expected:** Arizona SB 1229 restricts municipal design requirements, and will retrieve strongly on this wording - but it is STATE legislation and only engrossed. H.R. 1 contains nothing on municipal design. The answer must decline to answer the federal question from Arizona text, rather than presenting a state bill as federal law.

**Answer:**

No — I don't find anything in the retrieved federal excerpts that restricts municipal home design requirements.

The federal material here (H.R. 1) touches housing and homes only in unrelated ways: an exception to the percentage-of-completion accounting method for certain residential construction contracts [hr1-enrolled:70430:0], termination of the new energy efficient home credit [hr1-enrolled:70508:0], and Medicaid provisions on home equity limits and home or community-based services [hr1-enrolled:71108:0] [hr1-enrolled:71121:1]. None of these address municipal zoning, design standards, or land-use regulation.

What does address that subject is an **Arizona** bill, not federal law: Arizona S.B. 1229, which is engrossed (passed one chamber, not enacted). It would add A.R.S. §§ 9-461.19 and 9-461.20, barring a municipality from interfering with a home buyer's choice of features, floor plan, and interior/exterior design, and from requiring screening, walls, or fences on residential property [az-sb1229:1:2]. A companion section would bar municipalities from imposing design, architectural, or aesthetic requirements on single-family homes (with exceptions for historic districts), along with limits on minimum lot sizes, setbacks, and lot coverage — applicable to developments built after the effective date in municipalities over 70,000 people [az-sb1229:1:2]. Because that is state legislation and not yet law, it cannot answer a question about federal law.

If you are looking for a federal preemption of local design rules, I would need excerpts from a federal statute on housing or land use; nothing in this corpus supplies one.

---
