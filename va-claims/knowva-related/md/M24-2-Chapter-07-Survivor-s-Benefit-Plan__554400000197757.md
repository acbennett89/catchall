# M24-2 Chapter 07 Survivor's Benefit Plan

- Source: https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000197757/
- Article ID: 554400000197757 (KMPR-197757)
- Last modified: 28 Jul 2026 18:28:00.000 +0000

---

[Part 01 RSFPP / SBP Premium Deduction. 2](#_Toc100125553)

[Section 1.01 Overview. 2](#_Toc100125554)

[Section 1.02 Procedures. 2](#_Toc100125555)

[Part 02 SBP Overpayment 4](#_Toc100125556)

[Section 2.01 Overview. 4](#_Toc100125557)

[Section 2.02 Guidelines. 4](#_Toc100125558)

---

**Part 01 RSFPP / SBP Premium Deduction**

**Section 1.01 Overview**

1. The station should take action after receiving a properly executed DD Form 2891 (Department of Defense) or an authorization form from the U.S. Coast Guard (USCG) (USCG tasker is distributed via OFO, see Attachments Section for memo request samples), which authorizes recurring premium to be deducted from Compensation and Pension payments for application against the annuity of the Retired Servicemen’s Family Protection Plan (RSFPP) and/or Survivor Benefit Plan (SBP) Cost Deduction.  Deduction type and class will be as follows:

1. 15R/RSFPP and SBP Insurance Premiums - Army
2. 16R/RSFPP and SBP Insurance Premiums - Air Force
3. 17R/RSFPP and SBP Insurance Premiums - Navy
4. 18R/RSFPP and SBP Insurance Premiums - Marine Corps
5. 19R/RSFPP and SBP Insurance Premiums – U. S. Coast Guard (USCG)
6. 20R/RSFPP and SBP Insurance Premiums – U. S. Public Health Service (USPHS)
7. The National Oceanic and Atmospheric Administration (NOAA) – Currently, we have no deduction code for the NOAA deduction, please refer the NOAA deduction request the Office of Benefits – System via FIRE Salesforce.)

2. Only one SBP deduction type is allowed per compensation beneficiary.  A Veteran who has served in more than one branch can elect only one SBP deduction type.  It is extremely important that the proper deduction type and class code be used. Assignment of a wrong code to a transaction will cause the deduction to be paid to the wrong service department.
3. Deductions should be forwarded to the appropriate service via the Intra-Governmental Payment and Collection (IPAC).  The 15R, 16R, 17R and 18R deductions should be forwarded to the **Defense Finance and Accounting (DFAS)**, 19R, 20R and NOAA should be forwarded to the **USCG**.

**Section 1.02 Procedures**

SSD Finance uses a transaction type 18 to establish all SBP or RSFPP deduction types.  If the amount of benefits available is insufficient to satisfy the deduction amount, the transaction will be rejected and message 897, “Deduction Amount Exceeds Total Amount Available”, will be issued.  The DD Form 2891 or an authorization form and a VA letter explaining the rejection will be sent to the military service department. (Note: As of March 2018, transaction 18 deduction can be established with a future date.)

1. SSD Finance changes a deduction amount or terminates a recurring RSFPP for all deduction types or SBP deduction for Coast Guard (19R) or Public Health Service (20R) using transaction type 18A.
2. Changes to or terminations of SBP deductions **are automated** for Army (15R), Air Force (16R), Navy (17R), and Marine Corps (18R).  DFAS sends monthly updates, including the cost-of-living adjustments to eMPWR to adjust the deduction amounts automatically.
3. eMPWR generates a daily SBP Reject Report of any automated SBP deductions that were rejected.  Stations will review this report daily (after the DFAS monthly update which is on the 5th of each month) and the associated records to determine if the reject should be processed manually.  The report is available on the eMPWR-VA Reports Webpage under “Interface Reports”.  If no rejects are generated on a given day, the report will reflect “No Data” for that date.  The SBP Success Report, available under “Interface Reports”, lists the total number of automated SBP transactions at the end of each month and includes the total number of new, changed, or terminated SBP deductions that were automatically processed each month by deduction type.”
4. The Veteran or DFAS can make a request to start SBP or RSFPP deductions. To discontinue a deduction, only DFAS can make that change, except when:

1. Public Law 96-402, October 9, 1980, allows the retired member to discontinue participation in the Survivor Benefit Plan.
2. The claimant is suffering from a service-connected disability rated by the Department of Veterans Affairs (VA) as totally disabling; and has suffered from such disability while so rated for a continuous period of 10 or more years, or if so rated for a continuous period of not less than 5 years from the date of release from active duty.
3. Before VA can honor the request for discontinuance, VA must have on file a verification of the total disability rating and the effective date of such rating.

**Part 02 SBP Overpayment**

**Section 2.01 Overview**

1. SBP was established under [Public Law (PL) 92-425](https://www.gpo.gov/fdsys/pkg/STATUTE-86/pdf/STATUTE-86-Pg706.pdf) and is handled by Retired Pay Center (RPCs) of the Defense Finance and Accounting Service (DFAS) for survivors of Army, Navy, Air Force, and Marine Corps retirees, and the U.S. Coast Guard (USCG) for survivors of USCG, PHS, and NOAA retirees.
2. Per [10 U.S.C. § 1450(c](https://www.govinfo.gov/content/pkg/USCODE-2017-title10/html/USCODE-2017-title10-subtitleA-partII-chap73.htm)), *Payment of annuity: beneficiaries,* **prior to January 2021**, VA was required to offset DIC effective the start of the original DIC award if a survivor states that they were receiving or entitled to receive SBP, or if there is indication of entitlement.  [M21-1, Part XII, Subpart i, Chapter 4, Section C - Survivor Benefit Plan (SBP) Offsets](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000175221/M21-1-Part-XII-Subpart-i-Chapter-4-Section-C-Survivor-Benefit-Plan-SBP-Offsets?query=dic%20dfas) states that VA must verify with DFAS or USCG prior to generating an original DIC award to a survivor that an overpayment does not exist. If an overpayment exists VA must offset the original grant (or retro payment) of DIC in the amount of the overpayment.

**Section 2.02 Guidelines**

1. VA is not required to recoup SBP overpayments on a running award.  DFAS’ RPC should establish arrangement with the annuitant to reduce future SBP payments and recoup any overpayments.  Therefore, stations should not make any additional SBP offsets/deductions to DIC payments after the original award (or retro payment) is granted nor create any overpayment/debt.  The only exception was when DIC is paid as of the date last paid until a PTIVA response from DFAS is received per M21-1, IV.iii.3.F.2.d.  Once the DIC award is finalized, only the retro amount, if available, will be recouped.  Upon receiving a memo from the VSR, SSD finance will establish and authorize an 18/63 deduction (offset) to recoup from the retro award (which will be authorized after the 18/63 deduction is in place) and IPAC the funds to DFAS.
2. For example, a surviving spouse was granted DIC on January 2019. In July 2019, DFAS/VA discovered that there was no deduction set up to recoup the SBP causing an SBP overpayment on this running award.  Stations should not attempt to collect by creating any overpayment/debt.  If an overpayment/debt has been inadvertently created, this debt is not entitled for waiver right.
3. Effective October 2020, DFAS will no longer send the monthly DFAS 211 letters regarding SBP overpayments to the VA. The DFAS 211 letters are no longer being sent because Pension Management Center (PMC) employees have access to the Veterans Information Solution (VIS) and can send a request to DFAS using the Phone Transaction Interface Veterans Affairs (PTIVA) case form for information about the payment of SBP benefits to a surviving spouse.
4. Section 622 of the National Defense Authorization Act for Fiscal Year 2020 (NDAA 2020) was signed into law on December 20, 2019.  The NDAA 2020 modified the law that requires an offset of SBP payments for surviving spouses who are also entitled to DIC from VA. Under the previous law, a surviving spouse who receives DIC is subject to a dollar-for-dollar reduction of SBP payments, which can result in SBP being either partially or fully offset. The repeal will phase-in the reduction of this offset beginning on January 1, 2021, and culminating with elimination of the offset in its entirety on January 1, 2023. For the remainder of calendar year 2020, surviving spouses remain subject to the existing dollar-for-dollar offset of SBP payments by the amount of DIC paid by VA. After January 1, 2021, survivors subject to the “SBP-DIC Offset” will potentially see a change in their SBP payments. See M21-1, Part IX, Subpart iii, Chapter 2, Section D, and DoD offset of SBP, [10 U.S.C. 1450(c)](https://www.govinfo.gov/content/pkg/USCODE-2017-title10/html/USCODE-2017-title10-subtitleA-partII-chap73.htm).
5. The legislation phases in the repeal of the SBP-DIC offset from 2021 to 2023 are:

1. In 2020, surviving spouses will continue to have their SBP offset by the full amount of DIC they receive from VA.
2. In 2021, SBP will be reduced by no more than two-thirds of the amount of DIC rather than by the entire amount of DIC, even though eligible surviving spouses will continue to receive the full amount of DIC.
3. In 2022, SBP will be reduced by no more than one-third of the amount of DIC received.
4. In 2023, the SBP-DIC offset will be eliminated in total, so that surviving spouses eligible for both programs will receive both SBP and DIC in full, effective January 1 (paid as of February 1).

6. For example, in 2021, if an annuitant receives a monthly SBP annuity of $1200 from DoD/DFAS and becomes eligible to receive a monthly DIC award of $1500 from the VA, DoD/DFAS will deduct two-thirds of the amount of DIC ($1000) from the $1200 SBP and pay the remaining $200 to the annuitant. The annuitant will continue receive the full amount of DIC from the VA (in this example $1500).
7. Another example, in 2021, if a surviving spouse currently receives $1,500 from VA for DIC, but the gross SBP before offset is only $800, the surviving spouse will not see an increase in 2021 other than the normal annual cost of living adjustment (COLA). This is because the SBP amount, $800, is still less than the amount of DIC that would be subject to offset, which in this example would be $1,000 (i.e., $1,000 is two-thirds of the $1,500 DIC). Eventually, though, the surviving spouse will see an increase as the SBP-DIC offset is further reduced in 2022 and then completely eliminated in 2023.
8. When a currently serving member dies in the line of duty on active or inactive duty, the surviving spouse has the option to choose to have the SBP annuity paid directly to a dependent child rather than to receive the benefit for him or herself. This allows the surviving spouse to receive DIC from VA in full without it affecting the SBP payments. SBP paid to the child or children of the deceased service member is not offset by DIC. This provision is only allowed in situations in which the member died on active or inactive duty, in the line of duty, after October 7, 2001. While it remains in effect for now, on January 1, 2023, this option will go away in accordance with Section 622 of the NDAA 2020. Further, those annuities that were directed to a child rather than a surviving spouse will automatically revert to the surviving spouse, if they are still eligible, on January 1, 2023.
