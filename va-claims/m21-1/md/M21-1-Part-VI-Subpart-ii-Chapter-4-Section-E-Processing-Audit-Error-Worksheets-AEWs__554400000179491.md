# M21-1, Part VI, Subpart ii, Chapter 4, Section E - Processing Audit Error Worksheets (AEWs)

- Source: https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179491/
- Article ID: 554400000179491 (KMPR-179491)
- Last modified: 19 Nov 2025 19:24:12.000 +0000

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179490/)  [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179486/)

## Overview

---

**In This Section**

This section contains the topic “[Processing AEWs](#1).”

---

## 1.  Processing AEWs

---

**Introduction**

This topic contains information on processing AEWs, including

* [definition of an AEW](#1a)
* [how AEWs are generated](#1b)
* [maintaining control of AEWs](#1c)
* [automated AEW processing](#1d)
* [AEW types and messages](#1e)
* [initial review of an AEW](#1f)
* [adjusting an award based on an AEW](#1g)
* sequential receipt of AEWs that cover

  + [the exact same time period](#1h), and
  + [some but not all of the same entitlement months](#1i)
* special handling of AEWs

  + [that display an amount previously paid by the Defense Finance and Accounting Service (DFAS) (APPBD) or the Coast Guard (APPBC)](#1j), and
  + [include negative *Due From VA* amounts](#1k)
* special instructions

  + [about rounding down the amount in the *Due From VA* column](#1l), and
  + [for entitlement months of January 2014 or later](#1m)
* [processing AEWs that list a month in which the Department of Veterans Affairs (VA) adjusted disability compensation effective a day other than the first day of the month](#1n)
* processing AEWs

  + [with an amount withheld for military retired pay (MRP) that is equal to or greater than the amount shown in the *Due From VA* column](#1o)
  + [with an amount less than the amount shown in the *Due From VA* column](#1p)
  + [when VA withheld benefits from either the first day of the month to a later date within the same month or from a day within the month to the end of the month](#1q), and
  + [when the Veteran is eligible for concurrent receipt of the full amount of compensation and MRP based on length of service](#1r), and
* [notification of award adjustments associated with the processing of an AEW](#1s).

---

**Change Date**

November 19, 2025

---

**VI.ii.4.E.1.a . Definition: AEW**

An ***audit error worksheet*** (AEW) is a document containing data regarding a Veteran’s military retired pay (MRP) and entitlement to Concurrent Retirement Disability Pay (CRDP) or Combat-Related Special Compensation (CRSC).

---

**VI.ii.4.E.1.b . How AEWs Are Generated**

The table below describes how AEWs are generated.

| **Stage** | **Description** |
| --- | --- |
| 1 | When the Department of Veterans Affairs (VA) establishes or changes an award of disability compensation, VA electronically transmits the award data to the Defense Finance and Accounting Service (DFAS) and the Coast Guard. |
| 2 | DFAS and the Coast Guard audit the VA award data against MRP records.    ***Exception***:  Neither DFAS nor the Coast Guard audit VA award data against MRP records   * during time periods when the Veteran was not in receipt of MRP, or * if the VA award action did not increase the gross award amount for any month covered by the award action. |
| 3 | If the audit reveals an adjustment of the Veteran’s disability compensation is necessary based on entitlement to CRSC or CRDP, DFAS or the Coast Guard electronically transmits audit data to the Hines Information Technology Center (ITC). |
| 4 | The Hines ITC   * generates an AEW from the audit data * inserts the AEW into the corresponding electronic claims folder (eFolder), and * places the AEW under system control by establishing an 840 work item. |

---

**VI.ii.4.E.1.c . Maintaining Control of AEWs**

Follow the instructions in the table below upon receipt of an AEW.

| **Step** | **Action** |
| --- | --- |
| 1 | Is an end product (EP) 298 already pending to control the current or a previous AEW?   * If *yes*, go to the next step. * If *no*, establish EP 298, *CRSC/CRDP Processing*. |
| 2 | Add *Potential Under/Overpayment* as a special issue. |
| 3 | Clear the 840 work item that the Hines ITC established (if applicable). |

***Note***:  The proper date of claim for EP 298 is the date of the AEW, which is found in the upper right corner of the worksheet.

---

**VI.ii.4.E.1.d . Automated AEW Processing**

VA uses batch processing to automate the adjustment of many Veterans’ awards based on the audit data it receives from DFAS or the Coast Guard.  This process includes the generation of an award in the Veterans Benefits Management System – Awards (VBMS-A) and the generation and mailing of a decision notice to the Veteran.

***Exception***:  If an AEW contains more than 55 award lines, automatic generation of a decision notice during batch processing fails.  In such cases, Compensation Service’s MILPAY Staff sends an e-mail to the station of origination with a request to prepare the decision notice and mail it, along with a copy of the AEW, to the Veteran within 10 days.

***Note***:  The subject line of the e-mail from the MILPAY Staff will read *CRSC/CRDP Batch – Automatic Letter Kick-Out*.

---

**VI.ii.4.E.1.e . AEW Types and Messages**

The table below

* contains information about the various work items associated with AEWs, and
* describes the action to take upon receipt of each type of work item.

| **Work Item** | **Message** | **Reason for Generation of the Work Item** | **Action** |
| --- | --- | --- | --- |
| 840A | *CRSC/CRDP AEW –VETSNET Award Suspended* | The Veteran’s award was in a suspended status when the AEW was generated. | Postpone processing of the AEW until the Veteran’s award is no longer in a suspended status. |
| 840B | *CRSC/CRDP AEW –VETSNET Award Terminated* | The Veteran’s award was in a terminated status when the AEW was generated. | * If VA terminated the award because the Veteran died,    + treat the amounts due as potential accrued benefits, and   + follow the instructions in      - [M21-1, Part XI, Subpart ii, 3.E.3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174208/), if a claim for accrued benefits has been filed, or     - [M21-1, Part XI, Subpart ii, 3.C.1.c](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174206/), if a claim for accrued benefits has ***not*** been filed. * If VA terminated the award for any other reason, process the AEW according to the facts found. |
| 840C | *CRSC/CRDP AEW –VETSNET Award AR Exists* | An account receivable existed when the AEW was generated. | Process the AEW according to the facts found. |
| 840D | *CRSC/CRDP AEW –VETSNET Award Withhold Exists* | A withholding was in place when the AEW was generated. | Process the AEW according to the facts found. |
| 840E | *CRSC/CRDP AEW –VETSNET Award Negative VA Due* | The AEW contains a negative amount (a negative amount in the *Due From VA* column or an amount previously paid by DFAS (APPBD) or the Coast Guard (APPBC)). | Follow the instructions in   * [M21-1, Part VI, Subpart ii, 4.E.1.j](#1j), if the AEW contains an APPBD or APPBC amount, *or* * [M21-1, Part VI, Subpart ii, 4.E.1.k](#1k), if the AEW contains a negative amount(s) in the *Due From VA* column.   ***Note***:  When an AEW contains both an APPBD or APPBC amount *and* a negative amount in the *Due From VA* column, follow the respective guidance in both [M21-1, Part VI, Subpart ii, 4.E.1.](#1j)j and [k](#1k). |
| 840F | *CRSC/CRDP AEW – Award Appropriate Payment Due* | There were no special issues when the AEW was generated.    ***Note***:  This is the work item assigned to most AEWs; only this category of AEWs undergo the batch processing described in [M21-1, Part VI, Subpart ii, 4.E.1.d](#1d). | Follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.g](#1g). |

---

**VI.ii.4.E.1.f . Initial Review of an AEW**

Follow the instructions in the table below when performing an initial review of an AEW.

***Note***:  Defer processing an AEW until VA appoints a fiduciary if VA

* is withholding benefits to offset a Veteran’s receipt of MRP, and
* has rated the Veteran incompetent but has not yet appointed a fiduciary.

| **Step** | **Action** |
| --- | --- |
| 1 | Use VBMS to compare the amount of benefits the corporate record shows VA withheld each month (for MRP *only*) to the amounts shown in the *VA Withheld* column of the AEW for the same months to ensure they match.    If the amounts do *not* match,   * follow the instructions in the embedded table below, and * disregard the remaining steps in this table.   ***Notes***:   * VBMS displays the amount of benefits VA withheld each month on the CURRENT AND HISTORICAL AWARD INFORMATION page in VBMS. * If a change in either the *gross* amount of disability compensation or the amount of disability compensation VA is withholding takes effect on a date other than the first day of the month, *prorated* amounts will appear in the *VA Award* and *VA Withheld* columns of the AEW.  The prorated amounts will ***not*** match the amounts shown in the corporate record.  However, the amount in the *Due From VA* column of the AEW will be correct.   | **If …** | **Then …** | | --- | --- | | the difference between the amount in the *VA Withheld* column and the amount in the *Due From VA* column for each entitlement month displayed on the AEW matches the withholdings in the corporate record for each of the same months | clear the pending EP 298.  (No additional award action is necessary because VA has already released to the Veteran the amounts shown in the *Due From VA* column on the AEW.)    ***Important***:  If the award action that released the amounts in the *Due From VA* column did not result in the generation of a decision notice notifying the Veteran that VA released the funds due to entitlement to CRSC or CRDP, provide such notice to the Veteran. | | * the difference between the amount in the *VA Withheld* column and the amount in the *Due From VA* column for each entitlement month displayed on the AEW does ***not*** match the withholdings in the corporate record for each of the same months, and * the award action that released the amounts in the *Due From VA* column did *not* change the amounts in the *Total* column of the corporate record for the same months | adjust the Veteran’s withholdings so they match the difference between the amount in the *VA Withheld* column and the amount in the *Due From VA* column for each entitlement month displayed on the AEW.    ***Note***:  Under the circumstances described in this row, another AEW will ***not*** be generated. | | * the difference between the amount in the *VA Withheld* column and the amount in the *Due From VA* column for each entitlement month displayed on the AEW does ***not*** match the withholdings in the corporate record for each of the same months, and * the award action that released the amounts in the *Due From VA* column *changed* the amounts in the *Total* column of the corporate record for the same months | another AEW will be generated. Leave the EP 298 running and defer action until the new AEW is generated. When the new AEW is generated,   * clear the corresponding 840 work item, and * process the AEW under the pending EP 298. | |
| 2 | If the earliest entitlement month displayed on an AEW is *prior* to November 2009, check for an out-of-system CRSC/CRDP payment.    ***Rationale***:  VA made out-of-system CRSC/CRDP payments from October 2006 through November 2009. If the corporate record was never updated to reflect the payment, the potential for duplicate payments exists.    ***References***:  For more information on   * identifying out-of-system CRSC/CRDP payments, see the [*AEW Job Aid*](https://vbaw.vba.va.gov/bl/21/rating/rat00.htm), and * processing an AEW after VA made an out-of-system CRSC/CRDP payment, see [M21-1, Part VI, Subpart ii, 4.E.1.g](#1g) and [h](#1h). |
| 3 | Does the withholding in the corporate record exist ***solely*** to offset the Veteran’s receipt of MRP?   * If *yes*,    + disregard the remaining step in this table, and   + follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.g](#1g). * If *no*, go to the next step. |
| 4 | Follow the instructions in the table below.     | **If VA is withholding compensation …** | **Then …** | | --- | --- | | for a reason other than to offset the Veteran’s receipt of MRP for all of the entitlement months the AEW covers | * do ***not*** release the withholding * clear the EP 298, and * follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.s](#1s), for providing notice that the Veteran is not entitled to a retroactive payment of benefits. | | for a reason other than to offset the Veteran’s receipt of MRP for some but not all of the entitlement months covered by the AEW | * do ***not*** release the withholding for those months during which VA withheld compensation for a reason other than to offset the Veteran’s receipt of MRP, and * follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.s](#1s), for notifying the Veteran.   ***Important***:  When preparing the decision notice, select *The amounts the VA withheld for reasons other than retired pay* option in Step 5 of the AEW Assistant. | | both to offset the Veteran’s receipt of MRP and for another reason during the same month | * release that part of the withholding that is to offset the Veteran’s receipt of MRP up to the amount in the *Due From VA* column of the AEW for that month, and * follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.s](#1s), for notifying the Veteran.   ***Important***:  When preparing the decision notice, select *The amounts the VA withheld for reasons other than retired pay* option in Step 5 of the AEW Assistant. | |

***Note***:  An AEW may include entitlement months during which a Veteran was not eligible for CRSC/CRDP (such as when a Veteran’s combined disability rating is less than 50 percent).  DFAS and the Coast Guard include these entitlement months on the AEW when determining VA erroneously withheld compensation based on the Veteran’s receipt of MRP for those months, regardless of the Veteran’s eligibility for CRSC/CRDP.  Accordingly, the amounts in the *Due From VA* column of the AEW for those months are valid and should be treated the same as the amounts in the *Due From VA* column of the AEW for time periods during which the Veteran is eligible for CRSC/CRDP.

---

**VI.ii.4.E.1.g . Adjusting an Award Based on an AEW**

Follow the steps in the table below when it becomes necessary to adjust an award based on an AEW.

| **Step** | **Action** |
| --- | --- |
| 1 | Does the AEW display an entitlement month that is *earlier* than November 2009?   * If *yes*, go to the next step. * If *no*, go to Step 5. |
| 2 | Follow the instructions in the [*AEW Job Aid*](https://vbaw.vba.va.gov/bl/21/rating/rat00.htm) to determine whether an out-of-system adjustment was made during the time period the AEW covers.    ***Important***:  Only *automatic* out-of-system adjustments are reflected on the document titled *CRSC/CRDP One-Time Payment Notification from DFAS*. Confirm that no *manual*, out-of-system adjustment was made based on receipt of an AEW by checking the Veteran’s eFolder for a corresponding decision notice. |
| 3 | Was an out-of-system adjustment made during the time period the AEW covers?   * If *yes*, go to the next step. * If *no*, go to Step 5. |
| 4 | Update the PRIORS screen to reflect the out-of-system adjustment.    ***Reference***:  For more information on updating the PRIORS screen, see the [*AEW Job Aid*](https://vbaw.vba.va.gov/bl/21/rating/rat00.htm). |
| 5 | Subtract the amount (whether positive or negative) in the *Due From VA* column from the amount in the *VA Withheld* column to determine what the withholding (for MRP) will be for each month listed on the AEW.    ***Note***:  ***Subtracting*** a negative *Due From VA* column amount, as directed above, will ultimately have the effect of ***adding*** its value to the *VA Withheld* column amount.  ***Exception***:  If a prorated amount (as described in Step 1 of the table in [M21-1, Part VI, Subpart ii, 4.E.1.f](#1f)) appears in the *VA Withheld* column of the AEW, follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.n](#1n)-[r](#1r), to determine the amount of the withholding.    ***Reference***:  For more information on handling AEWs that include negative *Due From VA* amounts, see [M21-1, Part VI, Subpart ii, 4.E.1.k](#1k). |
| 6 | Enter the result of the calculation in Step 5 in the ADJUSTMENT AMOUNT field on the RETIRED PAY tab.    ***References***:  For more information on   * making entries on the RETIRED PAY tab or where to view the net effect of an award adjustment, see the *VBMS Awards User Guide*, and * processing an AEW, see the [*Military Pay*](http://vbaw.vba.va.gov/vbadod/retiredpay.asp) webpage. |
| 7 | Generate the award.    ***Important***:  Ensure the award generates from a date *no later than* the earliest date shown in the *Entitlement Month* column of the AEW. |
| 8 | Calculate the retroactive amount that VA owes the Veteran by totaling all the amounts displayed in the *Due From VA* column of the AEW. |
| 9 | Verify that the result of the calculation described in Step 8 equals the *Net Effect* of the award adjustment that is displayed in the award-processing application. |
| 10 | Follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.s](#1s) for notifying the Veteran of the award adjustment. |

---

**VI.ii.4.E.1.h . Sequential Receipt of AEWs That Cover the Exact Same Time Period**

Take the actions described in the table below if multiple AEWs exist that cover the exact same time period.

***Important***:  Anytime the table below refers to the amount of benefits VA owes a Veteran, it is referring to the ***net*** amount (the total of the amounts in the *Due From VA* column of an AEW *minus* the APPBD or APPBC (if present)).

| **If ...** | **And …** | **Then ...** |
| --- | --- | --- |
| none of the AEWs have been processed. | --- | process the *newest* AEW and disregard the older one(s). |
| one of the *older* of the AEWs was processed as an out-of-system adjustment | the amounts (including the amounts in the *Due From VA* column and the APPBD or APPBC (if present))and the dates on all the AEWs are identical | * reduce the withholdings (for MRP only), during the time period the AEWs cover, by the corresponding amounts displayed in the *Due From VA* column * update the PRIORS screen to reflect the out-of-system adjustment, and * follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.s](#1s) for providing notice that the Veteran is not entitled to additional benefits based on the *newer* AEW(s) (because VA previously paid the additional benefits that were due the Veteran when it processed the *older* AEW). |
| the *newest* AEW shows VA owes the Veteran *more* compensation than the older one | * process the *newer* AEW according to the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.g](#1g), and * update the PRIORS screen to reflect the out-of-system adjustment. |
| the *newest* AEW shows VA owes the Veteran *less* compensation than the older one | request guidance from the MILPAY Staff by sending an e-mail to [VAVBAWAS/CO/MILPAY](mailto:MILPAY.VBACO@VA.GOV). |
| * VA just recently processed one of the *older* of the AEWs (so recently that DFAS or the Coast Guard did not have the award data from the corresponding award adjustment when it performed the audit referenced in Stage 2 of the process described in [M21-1, Part VI, Subpart ii, 4.E.1.b](#1b)), and * the amounts in the *VA Award* column of the *newest* AEW are identical to the amounts in the *VA Award* column of the AEW that was just processed | the *newest* AEW shows VA owes the Veteran *less* compensation than the older one | request guidance from the MILPAY Staff by sending an e-mail to [VAVBAWAS/CO/MILPAY](mailto:MILPAY.VBACO@VA.GOV). |
| the *newest* AEW shows VA owes the Veteran *more* compensation than the older one | take award action to adjust the withholdings (for MRP only) so that the difference between the amount in the *VA Withheld* column and the *Due From VA* column for each entitlement month displayed on the *newer* AEW matches the withholdings in the corporate record for the same months. |
| one of the *older* of the AEWs was processed   * manually in the award-processing application, or * by the batch processing described in [M21-1, Part VI, Subpart ii, 4.E.1.d](#1d) | the amounts (including the amounts in the *Due From VA* column and the APPBD or APPBC (if present)) and the dates on all the AEWs are identical | * follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.s](#1s), for providing notice that the Veteran is not entitled to additional benefits based on the *newer* AEW(s) (because VA previously paid the additional benefits that were due the Veteran when it processed the *older* AEW), and * clear the corresponding 840 work item and controlling EP 298. |

***Reference***:  For more information about updating the PRIORS screen, see the [*AEW Job Aid*](https://vbaw.vba.va.gov/bl/21/rating/rat00.htm).

---

**VI.ii.4.E.1.i . Sequential Receipt of AEWs That Cover Some But Not All of the Same Entitlement Months**

Take the action described in the table below when multiple *unprocessed* AEWs exist that cover some but not all of the same entitlement months.  (It is acceptable to process these AEWs in the same award action.)

***Important***:

* If an APPBD/APPBC is displayed on only the *newest* AEW, follow the instructions in the table in [M21-1, Part VI, Subpart ii, 4.E.1.j](#1j), after following the instructions in the table below.
* Request guidance from the MILPAY Staff by sending an e-mail to [VAVBAWAS/CO/MILPAY](mailto:MILPAY.VBACO@VA.GOV) if

  + the *older* AEW(s) has(have) not been completely superseded by the newest AEW (as explained in the last row of the table below), and
  + an APPBD/APPBC is displayed on (any of) the *older* AEW(s).
* If all unprocessed AEWs are dated *prior* to June 1, 2011, the *newest* one supersedes the older one(s), regardless of the entitlement months any or all of the unprocessed AEWs cover.

| **If ...** | **Then ...** |
| --- | --- |
| the *newest AEW* displays an entitlement month | adjust the MRP withholding for that entitlement month based on that AEW. |
| any *but the newest* of the unprocessed AEWs displays an entitlement month that is *earlier* than the earliest entitlement month on the newest AEW | adjust the MRP withholding for that entitlement month using the *Due From VA* amount displayed on the *newest* of the AEWs that displays that entitlement month. |
| * an entitlement month appears on an *older*, unprocessed AEW that does not appear on the *newest* AEW, and * that entitlement month is *later* than the *earliest* entitlement month on the *newest* AEW | the *Due From VA* amount for that month is $0.00. |
| none of the entitlement months on the *older*, unprocessed AEW(s) are *earlier* than the earliest date on the *newest* AEW | ignore the older, unprocessed AEW(s) (including any APPBDs or APPBCs that appear on it(them)), since the newest AEW completely supersedes the older one(s). |

***Example***:

***Scenario***:

* The entitlement months of December 2004 through May 2005 appear on the *older* of two unprocessed AEWs.
* The following entitlement months appear on the *newest* of two unprocessed AEWs:

  + January 2005
  + March 2005, and
  + April 2005.

***Results***:

* The Veteran is entitled to the *Due From VA* amount displayed on the older AEW for December 2004.
* The Veteran is entitled to the *Due From VA* amounts displayed on the newest AEW for January, March, and April 2005.
* The *Due From VA* amount for February and May 2005 is $0.00.

---

**VI.ii.4.E.1.j . Special Handling of AEWs That Display an APPBD or APPBC**

If an AEW displays an amount to the right of the text *Amount Previously Paid by DFAS* or *Amount Previously Paid by Coast Guard*,

* follow the steps in [M21-1, Part VI, Subpart ii, 4.E.1.g](#1g) for routine processing of the AEW, but
* postpone authorization of the award adjustment pending completion of the steps in the table below.

***Notes***:

* The *Net Effect* of the award adjustment the award-processing application displays should still match the total of all amounts displayed in the *Due From VA* column on the AEW.
* To calculate the amount of the Veteran’s payment (so it can be provided in the corresponding decision notice), subtract the *Amount Previously Paid by DFAS* from the total of all amounts displayed in the *Due From VA* column on the AEW.

| **Step** | **Action** |
| --- | --- |
| 1 | Use the AEW Assistant to generate the *AEW Letter to Finance*. |
| 2 | E-mail a copy of the letter to the finance activity.    ***Note***:  The letter asks the finance activity to establish the APPBD or APPBC as a “collectible receivable.” |
| 3 | Upload a copy of the letter to the Veteran’s eFolder. |
| 4 | After the finance activity establishes the collectible receivable, refer the award adjustment for authorization.    ***No***t***e***:  The award adjustment must be authorized within *two days* in order to avoid Debt Management Office involvement. |

***Reference***:  For more information on AEWs involving DFAS payment, see [M21-1, Part VI, Subpart iii, 2.B.3.d](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179497/).

---

**VI.ii.4.E.1.k . Special Handling of AEWs That Include Negative Due From VA Amounts**

Follow the steps in the table below when processing an AEW that includes a negative *Due From VA* amount(s).

| **Step** | **Action** |
| --- | --- |
| 1 | Calculate the overpayment by totaling the negative *Due From VA* amounts on the AEW. |
| 2 | Was the overpayment the result of an administrative error as described in [M21-1, Part VI, Subpart i, 2.B.3.a and b](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179474/)?  (For example, was compensation withheld for a timeframe less than required, or at an amount less than directed by the [Retired Pay Withholding Calculator](https://vbaw.vba.va.gov/bl/21/Rating/Docs/Retired%20Pay%20Withholding%20Calculator.xlsx)?)   * If *yes*,   + clear the pending EP 298, and   + follow the instructions in [M21-1, Part VI, Subpart i, 2.B.3.g](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179474/) (to include issuance of notice of proposed adverse action). * If *no*, go to the next step.   ***References***:  For more information on   * erroneous payments and administrative errors, see [M21-1, Part VI, Subpart i, 2.B.1 and 3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179474/), and * adjusting an award affected by MRP, see [21-1, Part VI, Subpart ii, 4.B.2](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179488/). |
| 3 | Use the table below to determine the appropriate action.     | **If the net amount due is …** | **Then ...** | | --- | --- | | negative (the total of the negative *Due From VA* amounts ***exceeds*** the total of the positive *Due From VA* amounts) | * clear the pending EP 298 * establish EP 600 * issue notice of proposed adverse action in accordance with [M21-1, Part X, Subpart ii, 3.A.2](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177965/) * upon expiration of the adverse action proposal period take action to adjust the award as necessary, and * prepare and send a decision notice as described in [M21-1, Part VI, Subpart i, 1.B](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179469/).   ​​​​​​​***Important***:  Follow the instructions in [M21-1, Part X, Subpart ii, 3.B.3.c](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177966/) if a request for a hearing is received. | | positive (the total of the positive *Due From VA* amounts ***exceeds*** the total of the negative *Due From VA* amounts) | * follow the instructions in  [M21-1, Part VI, Subpart ii, 4.E.1.c](#1c), and * process the AEW using the procedures in [M21-1, Part VI, Subpart ii, 4.E.1.g](#1g). | |

***References***:  For more information on

* notice of proposed adverse action, see [M21-1, Part X, Subpart ii, 3.A](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177965/) and [B](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177966/), and
* eliminating an overpayment resulting from an administrative error when processing an AEW, see [M21-1, Part VI, Subpart iii, 2.B.3.f](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179497/).

---

**VI.ii.4.E.1.l . Special Instructions About Rounding Down the Amount in the Due From VA Column**

When processing older AEWs, the practice of rounding down the amount in the *Due From VA* column will depend on the adjustment date shown on the AEW.  The table below explains when rounding down is/is not appropriate.

| **If processing an AEW award line dated ...** | **Then ...** |
| --- | --- |
| prior to December 2013 | round down the amount in the *Due From VA* column. |
| December 2013 or later | do not round down the amount in the *Due From VA* column. |

***Important***:  ***Never*** round down the amount in the *Due From VA* column for entitlement months which include a rate change that takes effect on a day other than the first day of the month.

---

**VI.ii.4.E.1.m . Special Instructions for Entitlement Months of January 2014 or Later**

If the amount in the *VA Withheld* column of an AEW for an entitlement month of January 2014 or later differs from the amount in the *Due From VA* column for the same month by an amount less than one dollar,

* release the amount shown in the *VA Withheld* column for the same month, and
* include the following paragraph in the *What Is Your Entitlement* section of the decision notice:

****The enclosed audit error worksheet may show amounts due that differ from what we have calculated.  The worksheet is informational, showing VA may need to make an adjustment; however, we are required to double-check all calculations prior to releasing any funds to you.  Therefore the amount we pay will be based on our final calculations and may not match the totals from the worksheet.****

***Example***:

***Scenario***:  Entries on AEW are as follows:

* *Entitlement Month*:  March 2014
* *VA Withheld*:  $213.15
* *Due from VA*:  $213.00

***Action***:  Since the difference between the two amounts is less than one dollar, reduce the MRP withholding for March 2014 by $213.15.

***Note***:  The situation described in this block most commonly occurs when the subject of the AEW is a Coast Guard Veteran.

---

**VI.ii.4.E.1.n . Processing AEWs That List a Month in Which VA Adjusted Disability Compensation Effective a Day Other Than the First Day of the Month**

The amounts displayed on an AEW for a given entitlement month are applicable for the entire month.  If either the gross or net amount of a Veteran’s disability compensation changed effective a day other than the first day of the month,

* the amounts displayed on the AEW for the same month will not match up with VA’s corporate record, but
* the amount in the *Due From VA* column of the AEW for that month

  + will be correct, and
  + represents the amount VA must release to the Veteran for that month.

***Example***:  VA commonly reduces a Veteran’s benefits on a day other than the first day of the month when it removes a child from the Veteran’s award effective the day the child turns 18.

The methods for processing AEWs that list months in which either the gross or net amount of a Veteran’s disability compensation changed effective a day other than the first day of the month vary depending on a variety of factors.  Follow the instructions in

* [M21-1, Part VI, Subpart ii, 4.E.1.r](#1r), if

  + VA withheld benefits during a month after

    - December 31, 2013, in which the Veteran’s combined disability rating for service-connected (SC) disabilities was 50 to 90 percent, or
    - December 31, 2004, if the Veteran is totally disabled (on a schedular basis or on the basis of a total disability rating based on individual unemployability (TDIU)) due to SC disabilities, and
  + the Veteran retired based on length of service, or
* the table below in all other situations.

| **If …** | **Then follow instruction in …** |
| --- | --- |
| * VA withheld benefits to offset the Veteran’s receipt of MRP from the    + first day of the month to a later date within the same month, ***and***   + a day within the month to the end of the month, and * both withholdings are equal to or greater than the amount shown in the *Due From VA* column of the AEW | [M21-1, Part VI, Subpart ii, 4.E.1.o](#1o). |
| the amount of benefits VA withheld to offset the Veteran’s receipt of MRP is less than the amount shown in the *Due From VA* column of the AEW | [M21-1, Part VI, Subpart ii, 4.E.1.p](#1p). |
| VA withheld benefits to offset the Veteran’s receipt of MRP from either (not both) the   * first day of the month to a later date within the same month, or * a day within the month to the end of the month | [M21-1, Part VI, Subpart ii, 4.E.1.q](#1q). |

---

**VI.ii.4.E.1.o . Processing AEWs With an Amount Withheld for MRP That Is Equal to or Greater Than the Amount Shown in the Due From VA Column**

*Reduce* the amount of both withholdings (for MRP only) for the month in question by the amount shown in the *Due From VA* column on the AEW for the same month if

* there is a withholding in place for MRP

  + from the first day of the month, ***and***
  + from a day other than the first day of the month, and
* *each* of the amounts withheld for MRP is *equal to or greater than* the amount shown in the *Due From VA* column of the AEW for the same month.

***Note***:  Follow the instructions in [M21-1, Part VI, Subpart ii, 4.E.1.p](#1p) if *any* of the withholdings for MRP during the month in question are *less* than the amount shown in the *Due From VA* column of the AEW for the same month.

---

**VI.ii.4.E.1.p . Processing AEWs With an Amount Less Than the Amount Shown in the Due From VA Column**

Follow the instructions in the table below if

* there is a withholding in place for MRP

  + from the first day of the month, ***and***
  + from a day other than the first day of the month, and
* *any* of the amounts withheld for MRP are *less* than the amount shown in the *Due From VA* column of the AEW for the same month.

| **Step** | **Action** |
| --- | --- |
| 1 | Subtract the *smaller* of the amounts VA records show VA withheld (to offset the Veteran’s receipt of MRP) during the month in question from the *larger* amount that VA records show VA withheld for the same reason during the same month. |
| 2 | Subtract the *smaller* of the amounts VA withheld during the month in question from the amount shown in the *Due From VA* column on the AEW for the same month. |
| 3 | Divide the result of the calculation described in Step 2 by the number of days of the same month during which VA withheld the *larger* amount of benefits. |
| 4 | Multiply by 30 (days) the result of the calculation described in Step 3. |
| 5 | Subtract the result of the calculation described in Step 4 from the result of the calculation described in Step 1. |
| 6 | During the time period when the *smaller* withholding was in effect, withhold $0.00. |
| 7 | During the time period when the *larger* withholding was in effect, withhold the result of the calculation described in Step 5. |

***Example***:

***Scenario***:

* VA records show a withholding (to offset the Veteran’s receipt of MRP) of

  + $1,457.00, effective December 1, 2012
  + $1,491.00, effective September 9, 2013, and
  + $1,614.00, effective October 1, 2013.
* The *Due From VA* column on an AEW shows

  + $1,457.00 for the month of August 2013
  + $1,481.00 for the month of September 2013, and
  + $1,614.00 for the month of October 2013.

***Calculations***:  Following the procedures described in this block, the result of the calculation described in

* Step 1 is *$34.00* ($1,491.00 minus $1,457.00)
* Step 2 is *$24.00* ($1,481.00 minus $1,457.00)
* Step 3 is *$1*.*0909* ($24.00 divided by 22 (days))
* Step 4 is *$32.73* ($1.0909 multiplied by 30 (days)), and
* Step 5 is *$1.27* ($34.00 minus $32.73).

***Action***:  Withhold ***no*** benefits for the month of September until September 9, 2013.  Effective this date, begin withholding $1.27. Continue the withholding until October 1, 2013.

---

**VI.ii.4.E.1.q . Processing AEWs When VA Withheld Benefits From Either the First Day of the Month to a Later Date Within the Same Month or From a Day Within the Month to the End of the Month**

Follow the instructions in the table below to calculate the proper withholding when VA records show VA withheld benefits (to offset the Veteran’s receipt of MRP) from ***either*** (but not both)

* the first day of the month to a later date within the same month, or
* a day within the month to the end of the month.

| **Step** | **Action** |
| --- | --- |
| 1 | Divide the amount shown in the *Due From VA* column on the AEW for the month in question by the number of days VA withheld benefits. |
| 2 | Multiply by 30 (days) the result of the calculation described in Step 1. |
| 3 | Subtract the result of the calculation described in Step 2 from the amount of the withholding (to offset the Veteran’s receipt of MRP) that is shown in VA records for the same month.    ***Note***:  The result of the calculation described in this step represents the new withholding (to offset the Veteran’s receipt of MRP) for the month in question. |

***Example***:

***Scenario***:

* VA records show

  + a cost-of-living adjustment, effective December 1, 2004, with no withholdings
  + an adjustment in the Veteran’s award, effective September 26, 2005, with a withholding of $63.00 (to offset the Veteran’s receipt of MRP), and
  + a third adjustment, effective October 1, 2005, with a new withholding of $109.00 (to offset the receipt of MRP).
* The *Due From VA* column on an AEW for the Veteran shows

  + *$93.00* for the month of October 2005, and
  + *$10.00* for the month of September 2005.

***Calculations***:  Following the procedures described in this block, the result of the calculation described in

* Step 1 is *2* ($10.00 divided by 5 (days))
* Step 2 is *$60.00* (30 (days) multiplied by 2), and
* Step 3 is *$3.00* ($63.00 minus $60.00)

---

**VI.ii.4.E.1.r . Processing AEWs When the Veteran Is Eligible for Concurrent Receipt of the Full Amount of Compensation and MRP Based on Length of Service**

If the subject of the AEW is eligible for concurrent receipt of the ***full*** amount of disability compensation ***and*** MRP (based on length of service, ***not*** disability), eliminate the entire withholding (that VA established to offset the Veteran’s receipt of MRP) shown in VA records for the month in which VA changed either the gross or net amount of the Veteran’s disability compensation effective a day other than the first day of the month.

A Veteran is eligible for concurrent receipt of the full amount of disability compensation and MRP if ***one*** of the three ***sets*** of conditions listed in the table below is met.

| **Set** | **Conditions** |
| --- | --- |
| 1 | * The month in question is January 2005 *or later*. * The AEW shows the Veteran is authorized CRDP for the same month. * A VA rating of 100-percent disability or TDIU due to SC disabilities was in effect for the same month. |
| 2 | * The month in question is January 2014 *or later*. * The AEW shows the Veteran is authorized CRDP for the same month. |
| 3 | The AEW shows the Veteran is authorized 100 percent of CRSC for the month in question. |

***Note***:  Assume a Veteran retired based on length of service (rather than disability) if the

* MILITARY HISTORY segment in the Veterans Information Solution (VIS) displays *A*, *B*, or *C* in the column labeled *Ret Type*
* DFAS/CG PAYMENTS screen in VIS displays *A*, *B*, or *C* in the column labeled *Ret Type Cd*, or
* HUNT MBRENT screen in the Retired Casualty Pay Subsystem (RCPS) displays something ***other than***
  + no RET LAW field, or
  + a RET LAW field that is blank or contains one of the following entries:  *1201*, *1202*, *1204*, *1205*, or *0000*.

***References***:  For more information about using

* RCPS, see the [*Hunt User’s Guide*](https://vbaw.vba.va.gov/bl/21/products/docs/Huntug.pdf), and
* VIS, see the [*VIS User Guide*](http://vbaw.vba.va.gov/bl/21/publicat/docs/visug.pdf).

---

**VI.ii.4.E.1.s . Notification of Award Adjustments Associated With the Processing of an AEW**

After processing an AEW, notify the Veteran (or eligible survivor(s), when processing accrued benefits) who was the subject of the AEW of any associated award adjustments.

***Notes***:

* Enclose a copy of the AEW with the notice.
* Use of the AEW Assistant to generate the notice is mandatory.

***Reference***:  For more information on accrued benefits, see [M21-1, Part XI, Subpart ii, 3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174192/).

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179490/)  [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179486/)

[To Top](#top)
