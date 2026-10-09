# M24-2 Chapter 08 Returned Payment and Proceeds

- Source: https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000197758/
- Article ID: 554400000197758 (KMPR-197758)
- Last modified: 03 Aug 2026 12:03:52.000 +0000

---

[Part 01 Introduction. 2](#_Toc100070122)

[Section 1.01 Returned Payment 2](#_Toc100070123)

[Section 1.02 Common Return Payment Codes. 2](#_Toc98850446)

[Section 1.03 Re-issuing Limited Payabliity. 4](#_Toc100070125)

[Part 02 Returned Payment Reports. 5](#_Toc100070126)

[Section 2.01 Returned Payment Report for VETSNET Payments](#_Toc100070127)

[. 5](#_Toc100070127)[Section 2.02 Returned Payment Report - Education Payments](#2.02)

[Section 2.03 Unassociated and Proceeds Report “Reason” Descriptions. 5](#2.03)

[Part 03 Handling VETSNET/eMPWR-VA Returned Payments (Proceeds)](#part o3)

[Section 3.01 General](#_Toc100070131)

[Section 3.02](#3.02)[Returned Payments - Education](#3.02edu)

[Section 3.03 Proceeds Less Than Minimum (LTM) 8](#_Toc100070132)

[Section 3.04 Handling Proceeds at the SSD of jurisdiction](#_Toc100070133)

[. 10](#_Toc100070133)[Section 3.05 Reclamation](#3.04)

[Section 3.06 Proceeds Workflow](#3.05)

---

**Part 01 Introduction**

**Section 1.01 Returned Payment**

1. All payments, when returned to the Department of the Treasury, will be returned to the Philadelphia TRFC. The TRFC’s address is as follows:

Philadelphia Regional Finance Center

PO Box 51318

Philadelphia, PA  19115-6318

2. The TRFC will produce a file of returned payments and forward the file to the Hines Information Technology Center (HITC) for processing. (See [Section 2.03](#2.03) for a detailed Proceeds reason codes listing.)

**Section 1.02 Common Return Payment Codes**

1. **Reason 0 Non-entitlement**

1. Unavailable Check Cancellation Credit (UCC).
2. Reason code 0 is related to a tracer action when a check is outstanding at the time that Treasury receives the tracer request, and the check is cancelled with status, UCC, and a credit is sent to VA.
3. The credit is automatically processed, and it appears as a returned check in SHARE and accountable balance in the Enterprise Management of Payments, Workload, and Reporting VA (eMPWR-VA).
4. Please verify if the payee has cashed the initial check or not and determine if a 75A, 75B or 75C is needed.
5. Station must check TCIS on the payment status prior to releasing the reason 0 returned payment.
6. In chargeback situations, where an original check was cashed and a replacement check was issued, the Finance Center will create a debt in eMPWR-VA. The SSD of jurisdiction should wait for the overpayment to be created by the VBA Finance Center before taking any further actions on the reason 0 proceeds when a chargeback situation exists.
7. Reason code 0 proceeds related to Education payments are handled by the Muskogee SSD office.

2. **Reason 1 Undeliverable**

1. Moved or unclaimed
2. No such city or wrong address
3. Whereabouts unknown
4. DD/EFT account closed
5. No account

3. **Reason 2 Non-entitlement** -  Reportedly remarried.
4. **Reason 3 Non-entitlement** - Reportedly deceased.
5. **Reason 4 Non-entitlement** - Income limitation involved.
6. **Reason 5 Non-entitlement or Entitlement Undetermined**

1. Regional Office requests payment return from the financial institutions
2. Voluntary return by payee

6. **Reason 6 Non-entitlement** - Other.
7. **Reason 7 Non-entitlement** - Education advance payments.
8. **Reason 8 Non-entitlement** - Courtesy Disbursement Hold Check.
9. **Reason 9 Non-entitlement** - Returned Courtesy Disbursement Check.
   1. Effective June 11,2018, stop code C for tracer action which issues a courtesy check was disabled.
   2. Its replacement code is the stop code D which does not issue a courtesy check. (see Attachments Section below for BDN System Advisory - Disabling Claim Code "C" on RUPD)
10. **Reason 10 Non-entitlement**- Deceased Beneficiary
11. **Reason MC Miscellaneous Credit**- Misc. Credit from Treasury

    1. Treasury returned the funds to VA with the code Miscellaneous Credit (MC). SSD of jurisdiction must determine if the Veteran or Beneficiary is entitled to have the funds reissued.
12. **Reason M Manual Cancel Payment**

    1. When an improper retroactive award transaction is discovered, the VBA Regional Office can request for the retroactive award transaction to be cancelled (refer to M86P memo in VBMS) the same day the award was generated  through the VBA Finance Center. The funds for the canceled payment are placed into proceeds with a Reason M return code.
    2. The SSD of jurisdiction must determine the proper disposition of the Reason M proceeds.
13. **Reason B Limited Payability**

1. Limited Payability (LP) Cancellation.
2. In eMPWR-VA, this type of returned payments will be automatically returned to the appropriation and will not be shown on the proceeds reports.
3. Treasury provides VBA the LP cancellation file once a month.  The LP cancellation information will be in VETSNET SHARE or eMPWR-VA on the 14th month from the date of pay.

l. **Reason R Reclamation**

1. Credit from Treasury when VA enters a reclamation claim transaction (06ZR) or trace payment (06ZI) in eMPWR-VA.

**Section 1.03 Re-issuing Limited Payability**

1. If the Veteran/beneficiary is entitled for the benefits, the LP should be reissued after the LP cancellation information is posted in VETSNET SHARE and/or eMPWR-VA (on the 14th month from the payment date).
2. See Attachments Section below for Circular 20-92-12 for reference and Limited Payability SOP for additional guidance.
3. Verify with Benefit Eligibility Support Team *(*BEST) to ensure that the Veteran/beneficiary is still entitled for the benefit.
4. Ensure that there is no previous cancellation and reissuance of the LP payment:

   1. Review the Treasury Check Information System (TCIS) information to determine the status on the payments.
   2. Review SHARE and/or eMPWR-VA for the payment history.
   3. Perform a paid and due audit to ensure that the LP payments have not been reissued in one single payment, if needed.
   4. If the Veteran/beneficiary has a debt, apply the LP payments toward the debt (on the same payee and program type only) with a 08L transaction, and reissue the balance of the LP payments, if any. **Note: Before applying the LP payment toward the debt, SSD** **of jurisdiction** **must ensure that due process has been met and no other mitigating circumstances, e.g., repayment agreement, pending waiver decision, etc., are present.**
   5. Send a Limited Payability letter (see Attachments Section below)  to the Veteran/beneficiary informing him/her of the action taken.
5. There is a 6-year time limitation on the claims of the LP payments (6-year time limitation is based upon the original issuance date of the check) unless the payee deceased prior to cashing the checks. (Refer to [VAOPGCPREC 19-95](https://www.va.gov/ogc/docs/1995/Prc19-95.pdf))  LP payments for deceased Veteran/beneficiary should be handled in accordance with [38 CFR §3.1003](https://www.ecfr.gov/current/title-38/chapter-I/part-3/subpart-A/subject-group-ECFRa6cd81dd03d3544/section-3.1003) - Returned and canceled checks and [38 CFR 3.1000](https://www.ecfr.gov/current/title-38/chapter-I/part-3/subpart-A/subject-group-ECFRa6cd81dd03d3544/section-3.1000) - Entitlement under 38 U.S.C. 5121 to benefits due and unpaid upon death of a beneficiary.
6. Do not reissue LP payments that exceeded the 6-year time limitation (based on original issuance date).
7. If there are additional LP payments in the system and within the 6-year time limitation (based on original issuance date), issue a  VA Form 20-8992 (See Attachments Section below) to inform the Veteran/beneficiary on the voided checks.  A signed VAF 20-8992 by the Veteran/beneficiary and voided checks (if applicable) are required to process reissuance of the LP payments.
8. For beneficiary travel LP payments, FMS does not systematically provide a notification to the beneficiary.  Review the FMS accepted document listing report and XR transactions for this type of cancellations.

**Part 02 Returned Payment Reports**

**Section 2.01 Returned Payment Report for VETSNET Payments**

1. VETSNETS returned payments, including C&P, Chapter 31, Chapter 21/39, and Chapter 18, are compiled into the Unassociated/Proceeds Report in eMPWR-VA.
2. C&P Unassociated/Proceeds Report and the Chapter 21/39 Return Payment Report are generated daily and listed under the C&P eMPWR-VA Reports – All Programs, Finance Operations Reports section.
3. For Chapter 31, the Ch 31 Unassociated/Proceeds Report is generated weekly on Friday and listed under the eMPWR-VA Reports – All Programs, Finance Operations Reports section.
4. The report can be viewed online and queried by the SSD of jurisdiction. *Note: The Unassociated/Proceeds Report consists of items that are not related to returned payments, if stations are working on returned payments that are in proceeds, stations should download the file as a CSV document and filter the spreadsheet to "Proceeds" under the "Type" column.*
5. SSD of jurisdiction must review the C&P, Chapters 31, 18, 21 and 39 reports weekly to determine the disposition of the payments.
6. See [Part 03](#part o3) below for procedures on handling VETSNET returned payments (proceeds).

**Section 2.02 Returned Payment Report - Education Payments**

1. The Education returned payments report is generated by Hines IT daily.
2. The Unassociated/Proceeds Report and Unidentified Beneficiary Report is available in eMPWR-VA Reports and can be accessed by the two RPOs and the SSD of jurisdiction for review and release of Education returned payments.

**Section 2.03 Unassociated and Proceeds Report “Reason” Descriptions**

|  |  |
| --- | --- |
| Description | Reason Code |
| Unavailable Check Cancellation Credit | 0 |
| Undeliverable | 1 |
| Reportedly Remarried | 2 |
| Reportedly Deceased | 3 |
| Income Limitation | 4 |
| Cancelled per VA's Request | 5 |
| Other Reasons | 6 |
| B7 Holds | 7 |
| Courtesy Disbursement Hold Check | 8 |
| Returned Courtesy Disbursement Check | 9 |
| Deceased Beneficiary | 10 |
| Miscellaneous Credit | MC |
| Manual Cancel Payment | M |
| Specially Adapted Housing/Special Home Adaptation | SAHSHA |
| Fiduciary Necessary - Not Established | 101 |
| Retroactive Amounts, Agreed Limit By Fiduciary - Authorization Necessary | 102 |
| Unidentified Account | 301 |
| Over Collection | 302 |
| To Station | 1018 |
| From Station | 1019 |
| Recurring Paid Other Than Monthly-Annual Payment | 01A |
| Greater Than Maximum | 01G |
| Less Than Minimum Or Re-established | 01L |
| Payment - No Address Information | 01P |
| Recurring Paid Other Than Monthly-Quarterly Payment | 01Q |
| Recurring Paid Other Than Monthly-Semi Annual Payment | 01S |
| Unidentified Account-CARS | 301C |
| Gratuitous | 70S1 |
| Private Source | 70S2 |
| Advance Pay Returned | 7E |
| Check Intercept | A |
| Limited Payability Cancellation | B |
| Expenditure Transfer | ET |
| OFAC Restricted | OFAC |
| Consolidated Payment Returned | PFOP |
| Insurance Premium Refund | PREM REF |
| Returned Payments Previously Processed | PREV CHK |
| Reclamation (See [Section 3.04](#3.04) for details.) | R |
| Burial Allowance Returned Payment | RETPAYBUR |
| Clothing Allowance Returned Payment | RETPAYCA |
| Fiscal Returned Payment | RETPAYFISC |
| Medal of Honor Returned Payment | RETPAYMOH |
| No Matching Returned Payment | RETPAYNM |
| 06G Special Returned Payment | RETPAYSPEC |
| Termination (Non-Death) Returned Payment | RETPAYTERM |

**Part 03 Handling VETSNET/eMPWR-VA Returned Payments (Proceeds)**

**Section 3.01 General**

1. This section pertains to the handling of VETSNET/eMPWR-VA proceeds under the Regional Office’s (RO) jurisdiction.
2. As of October 1, 2020, all ROs have been paired with a Benefit Eligibility Support Team (BEST). Non-rating workload which includes the reviewing of returned payments (proceeds) will require SSD of jurisdiction to coordinate their efforts with their BEST to assure the correct disposition for returned payments. See Attachments Section below for the Non-Rating Resource Job Aid.
3. The BEST and SSD of jurisdiction are responsible for the proper handling of proceeds.  As a team, SSD of jurisdiction and the BEST must work together to ensure that all appropriate actions are implemented to properly dispose of proceeds.
4. An EP 290, EP 930 or EP 810 is created on each proceed for return reason 1, 2, 3, 4, 5, 6, or 10 and routed via NWQ to BEST/PMC. The BEST/PMC is responsible for updating the award status from "suspended" to "authorized" or "terminated", as appropriate. If an award was processed in error, DO NOT process a 75 transaction. BEST/PMC must amend the award. If the award is not correct and BEST/PMC cannot process a corrected award, SSD of jurisdiction must obtain permission from the Office of Benefits (OOB) with justification from the C&P Award Service Mailbox in Central Office, before processing a fiscal transaction on the file.
5. After BEST processes the award and clears the EP 290, EP 930 or EP 810, and the proceed (for reasons 1, 2, 3, 4, 5, 6, or 10) remains with a balance on the record, BEST/PMC will prepare a Proceed Memo for the record outlining the outstanding balance needing finance action. This memo will be uploaded to the VBMS eFolder and a FIRE case will be routed to the SSD of jurisdiction to take disposition action on the funds.
6. Not all proceed return reasons require an EP and review by BEST/PMC. The SSD of jurisdiction must review proceed return reasons to identify and clear funds which are outside the scope of BEST/PMC.

1. All finance transactions for clearing proceeds referred from the BEST/PMC through the FIRE system must be supported by a Proceed Memo. The status of the Proceed FIRE case will automatically be updated upon closure of the EP, indicating the record is ready for finance action.
2. Upon assignment of a proceed case in the FIRE system, the SSD of jurisdiction must verify the current award status prior to processing a 75 transaction to clear the proceeds. If the status of the award is suspended or terminated, and the Proceed Memo in VBMS does not provide sufficient disposition instructions, the SSD of jurisdiction should inquire with the BEST/PMC individual who closed the EP for further guidance.

7. Upon completion of the fiscal transaction, the SSD of jurisdiction must upload the supporting documentation into the claims folder within Veterans Benefits Management System (VBMS).
8. Burial Returned Payments.  Burial Awards that are returned from Treasury will offset any burial receivable and create a proceed for the remaining funds.  When this occurs, you will receive Message 607 “Miscellaneous Returned Payment” in your station’s Awards Mailbox.  When this message is received, your station should research entitlement and take action to release the burial payment proceed via an appropriate 75 transaction.  All burial return payments will be directed to eMPWR-VA for processing regardless of where the payment originated (eMPWR-VA).  Returned burial payments in which the originating payment cannot be matched in eMPWR-VA will be returned to Appropriation.
9. Station 339 Denver is responsible for all Chapter 18 Spina Bifida proceeds.  If Chapter 18 proceeds are erroneously assigned to your station, forward them to Station 339.
10. Station 335 St Paul is responsible for all Specially Adapted Housing/Special Home Adaptation (SAH/SHA) and Chapter 31 Independent Living Housing Adaption Grant (ILHA) proceeds. If the SAHSHA or ILHA proceeds are erroneously assigned to your station, forward them to Station 335.
11. Unavailable Check Cancellation Credit and Returned Courtesy Disbursement Check (Reason 0 & 9) should be handled by SOJ finance which is responsible or who processed the associated tracer.
12. Reclamations should be handled by the Debt Management Center or SSD of jurisdiction, referring to Section 3.04 for details.
13. If a manual fiscal transaction (i.e., 75A, 06A) is returned and creates proceeds with an award in authorized status and the Proceed FIRE case description indicates No EP Established, finance should take action to clear the proceed as VSC/BEST action is not required to release funds.
14. If there is no active EP associated with a proceed, finance should look in VBMS to identify if the EP was closed by an individual in BEST/PMC, then reach out to the individual who closed the EP and CC the associated BEST mailbox if a Proceed Memo is not in VBMS.

**Section 3.02 Returned Payments – Education**

1. This section pertains to the handling of Education proceeds under the Regional Processing Offices (RPO).
2. As of July 8, 2024, eMPWR-VA is the subsidiary system of record for all Education payments.
3. The RPO and SSD of jurisdiction are responsible for the proper handling of Education proceeds.  As a team, SSD of jurisdiction and the RPO must work together to ensure that all appropriate actions are implemented to properly dispose of both Identified and Unidentified proceeds.

   1. Veterans Claims Examiner (VCE) and the Support Services Division (SSD) within the two RPOs are responsible for reviewing the Unassociated/Proceeds Report – Education.
   2. The VCE is responsible for releasing Education proceeds by award action or through a change of address, as applicable.
   3. For Identified Returned Payment, the VCE must resolve the award issue, and if the proceed remains with a balance in the record, the proceed case will be routed to the associated SSD of jurisdiction  to be cleared via a 75 transaction (i.e. 75A to release funds to the Veteran or Beneficiary, 75B to apply funds toward an existing debt, or 75C to return the funds to appropriation) to release the funds.
   4. Veterans Claims Examiner (VCE) RPOs are responsible for reviewing the Unidentified Beneficiary Report in eMPWR-VA.
   5. VCE must determine if the unidentified returned payment’s beneficiary is entitled to the funds, if not entitled, the funds will remain in appropriation. If the beneficiary is entitled, the VCE will refer the case to the SSD of jurisdiction for manual transactions (i.e. 06A or 08E).

**Section 3.03 Proceeds Less Than Minimum (LTM)**

1. Less than minimum (LTM) is referring to a returned payment with the 01L reason code.  *Note: The LTM procedures do not apply to return payments with other reason codes (e.g. 1, 3, 5, or 6) with less than $1.00 for check payment or less than $0.10 for DD/EFT payments.*
2. LTM Proceeds (less than $1.00 for check payments and less than $0.10 for DD/EFT payments) will automatically attach to the next outgoing recurring award payment for the beneficiary in eMPWR-VA.  LTM proceeds (01L) belonging to recipients of authorized awards should not be displayed on the Unassociated/Proceeds report.  If there are LTM proceeds on your list, you can ONLY apply them to existing debts (75B) when appropriate.  If you release them using a 75A transaction, that transaction will fail and the proceeds will never automatically attach to the next payment. *Note: LTM with no running award can be released with the 75A transaction.*
3. DO NOT send these funds to the appropriation unless the payee is no longer eligible for benefits.  If the beneficiary does not have a current running award, the proceeds may only be cleared with a 75B (Apply Proceeds to Receivable) or 75C (Return Proceeds to Appropriation) transactions.
4. Proceeds for awards that are paid on an Other Than Monthly (OTM) schedule (Quarterly, Semi Annually, or Annually) will automatically release on the OTM schedule and should not be released with a 75-Release of Proceeds Transaction unless the award is terminated.
5. If the LTM proceeds do not automatically attach to the next outgoing payment, or if the OTM proceeds do not release on schedule, the users should contact Finance Services Division through the FIRE application.
6. Procedures are summarized as follows:

|  |  |  |
| --- | --- | --- |
| **Reason Code** | **Award Status** | **Action Needed** |
| 01L - Less than minimum or reestablished    *Note:  These procedures only apply to proceeds with the reason code “01L”.  If you have proceed that is less than $0.10 for EFT and $1 for check payment and the reason code is not “01L”, e.g.”1 “or “3”, follow the applicable procedures for that reason code.* | Authorized | 1. Apply funds to existing debts (75B), if any; 2. Otherwise, no action is needed; 3. If it does not attached to the next outgoing recurring payment with a total amount larger than the minimum thresholds ($0.10 EFT/$1 check), inform Fiscal Operations through the FIRE application. |
| Terminated or Suspended | 1. Apply funds to existing debts (75B), if any; 2. Return funds to the appropriation (75C); or 3. Return funds to Veteran/beneficiary (75A) - If the aggregated proceeds amount on multiple returned payments for a Veteran/beneficiary is **more** than the minimum thresholds ($0.10 EFT/$1 check), release multiple returned payments to the Veteran/beneficiary in one 75A transaction; otherwise, return funds to the appropriation (75C). |
| None | Research to determine the current status. |
| 01Q Recurring Paid other than monthly - quarterly payment    01A – Recurring Paid other than monthly - annual payment    01S Recurring Paid other than monthly -  semi-annual payment | Terminated or Suspended | 1. Apply funds to existing debts (75B), if any; 2. Return funds to the appropriation (75C); or 3. Return funds to Veteran/beneficiary (75A) - If the aggregated proceeds amount on multiple returned payments for a Veteran/beneficiary is **more** than the minimum thresholds ($0.10 EFT/$1 check), release multiple returned payments to the Veteran/beneficiary in one 75A transaction; otherwise, return funds to the appropriation (75C). |
| None | Research to determine the current status. |

**Section 3.04 Handling Proceeds at the SSD of jurisdiction**

The SSD of jurisdiction will use the following table to determine the appropriate action to take when clearing the accountable balances.

|  |  |  |  |
| --- | --- | --- | --- |
| **Award Status** | **Return Reason Code** | **Existing Debt** | **Action Needed** |
| Active or Terminated | 0 | Yes | Check TCIS to determine the payment status.  When the Veteran/beneficiary is entitled for the payment (e.g., did not cash the initial check):  1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify that the Veteran/beneficiary’s current payment address is accurate to avoid a bad address return.  3. Apply funds to existing debts (75B)  4. Return the balance to the Veteran/beneficiary (75A), if any. |
| Active or Terminated | 0 | No | Check TCIS to determine the payment status.  When the Veteran/beneficiary is entitled for the payment (e.g., did not cash the initial check):  1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify that the Veteran/beneficiary’s current payment address is accurate to avoid a bad address return.  3. Return the funds to the Veteran/beneficiary (75A). |
| Active or Terminated | 0 | Yes/No | Check TCIS to determine the payment status.  When the Veteran/beneficiary is NOT entitled for the payment:  1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Return funds to the appropriation (75C). |
| Suspended | 0 | Yes/No | 1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify that there is an active EP 290 or EP 930 for the case and await disposition instructions from the BEST who will need to resume the award. |
| None | Any reason code | Yes/No | 1.  Research to determine the current award status.  2.  Perform the pertinent procedures based on the award status. |
| Suspended | 1 | Yes or No | 1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify there is an active EP 290 or EP 930 for the case and await disposition instructions found on the Proceed Memo from BEST or PMC in VBMS.    Large retroactive EFT payments or payments larger than the bank’s EFT limit may also be returned as undeliverable.  Check VBMS notes for additional notes; complete a Change of Address to release the payment to the physical address; and update the direct deposit information as necessary. |
| Suspended | 3 or 10 | Yes or No | 1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify there is an active EP 290 or EP 930 for the case and await disposition instructions found on the Proceed Memo from BEST or PMC in VBMS. |
| Suspended | 5 or 6 | Yes or No | 1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify there is an active EP 290 or EP 930 for the case and await disposition instructions found on the Proceed Memo from BEST or PMC in VBMS. |
| Active or Terminated | 1 | Yes or No | 1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify there is an active EP 290 or EP 930 for the case and await disposition instructions from BEST. |
| Active or Terminated | 3 or 10 | Yes or No | 1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify there is an active EP 290 or EP 930 for the case and await disposition instructions found on the Proceed Memo from BEST or PMC in VBMS. |
| Active or Terminated | 5 or 6 | Yes or No | 1. Verify the current award status (e.g. Authorized, Terminated, or Suspended).  2. Verify there is an active EP 290 or EP 930 for the case and await disposition instructions found on the Proceed Memo from BEST or PMC in VBMS. |

**Section 3.05 Reclamation**

1. Reason R proceeds in terminated status are under DMC’s jurisdiction and are normally a result of reclamation action by DMC to recover payments issued after the death of the beneficiary. SSD of jurisdiction should not work on these cases until directed by DMC.
2. If SSD of jurisdiction is assigned a reclamation case from DMC, the SSD of jurisdiction should perform the proper research on the correct disposition for reclamation proceeds before releasing the funds (e.g. Reclamation amount collected by DMC were in excess of the reclaimed amount being requested from the Financial Institution (FI) or estate, hence a refund to the estate or FI would be warranted).

   1. If a debt exists, the SSD of jurisdiction should apply all the funds toward the debt, i.e. 75B, any remaining funds should be returned to the Veteran, i.e. 75A, or placed into appropriation, i.e. 75C, as appropriate.
   2. If the SSD of jurisdiction is uncertain on the proper disposition of the reclamation funds, the SSD of jurisdiction should communicate with DMC using the LEAF system <https://leaf.va.gov/NATIONAL/189/dmcgencorrreq/> for additional information and/or perform a paid and due audit to determine if the Veteran is entitled to the reclaimed amount.  If it is determined that the Veteran is not entitled based on the paid and due audit, the SSD of jurisdiction should place the funds back into appropriation using transaction 75C.
   3. In cases where the reclaimed amount was erroneously sent into appropriation, i.e. 75C, the SSD of jurisdiction who conducted the administrative error is responsible for reissuing the funds to the Veteran, estate, financial institution, or beneficiary using transaction 06A.
3. Reason R proceeds in authorized status. SSD of jurisdiction must review the Reason R proceeds in authorized status listed under their station number to determine the proper disposition of the reclamation proceeds (e.g. process an 75A to the Veteran and/or Beneficiary).

   1. If the SSD of jurisdiction is uncertain on the proper disposition of the reclamation funds, the SSD of jurisdiction should communicate with VBAFC or the RO that initiated the tracer action which resulted in the reclamation credit from Treasury (e.g. credit from Treasury when VA traces a paper check that was altered and deposited by non-entitled persons).
   2. If a debt exists, the SSD of jurisdiction should apply all the funds toward the debt, i.e. 75B, any remaining funds should be returned to the Veteran, i.e. 75A, or placed into appropriation (i.e. 75C), as appropriate.
   3. In cases where the reclaimed amount was erroneously sent into appropriation, i.e. 75C, the SSD of jurisdiction who conducted the administrative error is responsible for reissuing the funds to the Veteran, estate, financial institution, or beneficiary using transaction 06A.

**3.06 Proceeds Workflow**

1. Effective September 1, 2023, the new Proceed Workflow functionality went live for all stations. The Proceed Workflow automates the flow of work between VSC/BEST/PMC and the SSDs for purposes of managing proceed activity. The Proceed workflow leverages the National Work Queue (NWQ) and the Finance Inquiry Resolution Engine (FIRE) to route work between divisions within the RO. Refer to the [Proceeds Workflow Job Aid](https://va.lightning.force.com/lightning/o/Knowledge__kav/list?filterName=EMPWR_Published_Articles) for details on the workflow.
