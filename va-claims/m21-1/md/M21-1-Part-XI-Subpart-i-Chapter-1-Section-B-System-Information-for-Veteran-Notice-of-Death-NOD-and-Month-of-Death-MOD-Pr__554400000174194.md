# M21-1, Part XI, Subpart i, Chapter 1, Section B  - System Information for Veteran Notice of Death (NOD) and Month of Death (MOD) Processing

- Source: https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174194/
- Article ID: 554400000174194 (KMPR-174194)
- Last modified: 16 Sep 2025 13:29:20.000 +0000

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174187/)  [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174195/)

## Overview

---

**In This Section**

This section contains the following topics:

| **Topic** | **Topic Name** |
| --- | --- |
| 1 | [Command for Veteran NOD Processing](#1) |
| 2 | [Existing Beneficiary Identification and Records Locator Subsystem (BIRLS) Records and Veteran NOD Processing](#2) |
| 3 | [Processing MOD Payments With Other Death Benefits](#3) |
| 4 | [Exhibit 1:  MOD Memorandum](#4) |

---

## 1.  Command for Veteran NOD Processing

---

**Change Date**

December 12, 2022

---

**XI.i.1.B.1.a . Veteran NOD Processing**

Process a Veteran's notice of death (NOD) under the FIRST NOTICE OF DEATH (FNOD) command in Share.  The FNOD command clears any pending end products (EPs), except for several fiduciary oversight EPs.

***Important***:

* Do not clear EPs processed by the fiduciary hubs (hubs) that remain pending after FNOD.  Hub EPs are typically identified with the word *Fiduciary* as the first word in the claim label name.  The hub will clear these EPs upon completion of fiduciary oversight actions.
* Process the NOD and establish any survivors claim, if applicable.

***References***:  For more information on

* processing a NOD for a
  + Veteran, see [M21-1, Part XI, Subpart i, 1.A](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174187/), and
  + non-Veteran, see [M21-1, Part XI, Subpart i, 1.D](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174196/), and
* establishing claims in
  + the Veterans Benefits Management System (VBMS), see [M21-1, Part II, Subpart iii, 3.A.1.d](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174881/), and
  + Share, see [M21-1, Part II, Subpart iii, 3.A.1.e](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174881/).

---

## 2.  Existing BIRLS Records and Veteran NOD Processing

---

**Introduction**

This topic contains information on working with existing BIRLS records and Veteran NOD processing, including

* [Veteran NOD processing steps to include working with the MONTH OF DEATH and PRESIDENTIAL MEMORIAL CERTIFICATE screens](#2a)
* [modifying existing dependent spouse of record on MONTH OF DEATH screen](#2b)
* [identifying MOD cases paid by batch](#2c)
* [amending the COMPENSATION AND PENSION DEATH (CPD) SPOUSE tab created by the automated MOD process](#2d)
* [reviewing the ALL AWARDS page for MOD payments](#2e)
* [granting entitlement to MOD payment only](#2f)
* [denying entitlement to MOD](#2g)
* [when the system finds multiple records during the NOD processing](#2h)
* [disposition of Veteran NOD data prints](#2i), and
* [assigning new file numbers during the Veteran NOD processing](#2j).

---

**Change Date**

September 16, 2025

---

**XI.i.1.B.2.a . Veteran NOD Processing Steps to Include Working With the MONTH OF DEATH and PRESIDENTIAL MEMORIAL CERTIFICATE Screens**

From the Share VBA READY screen, select the FNOD command and enter the Veteran’s

* file number
* name, and
* service information if sufficient evidence accompanies the NOD.

If you do not know the Veteran’s file number, enter

* the Veteran’s Social Security number (SSN), and
* as much additional identifying information as possible to avoid creating duplicate Beneficiary Identification and Records Locator Subsystem (BIRLS) records.

Follow the steps in the table below when the system locates an existing BIRLS record for a Veteran.

| **Step** | **Action** |
| --- | --- |
| 1 | Review the system to determine if the Veteran has a running award.   * If *yes*, go to the next step. * If *no*, go to Step 6. |
| 2 | Review the system to see if there is a *living* spouse of record.   * If *yes*, go to the next step. * If *no*, go to Step 6. |
| 3 | Use the SSA INQUIRY function within VBMS to confirm whether the spouse is still living.   * If *yes*, go to Step 6. * If *no*, go to the next step. |
| 4 | Save the SSA INQUIRY results, showing the spouse’s date of death, in the electronic claims folder (eFolder). |
| 5 | Enter the spouse’s date of death into VBMS. |
| 6 | Select the FNOD command and enter the Veteran's file number or SSN, first name and last name, and click the SUBMIT button.    Verify that the information on the VETERAN IDENTIFICATION DATA (VID) screen for the Veteran is complete and accurate (if not, modify), and enter the following:   * the Veteran's date of death * the applicable cause of death in the CAUSE OF DEATH field:    + *UNKNOWN*   + *NATURAL*   + *COMBAT*, or   + *OTHER*, and  * a *Y* in the DEATH IN SERVICE field *if* the evidence shows the Veteran died in service.   ***Important***:  The name entered into the FNOD command *must* be identical to the name on the BIRLS record to enable the UPDATE button on the VID screen.    ***Note***:  If it is determined that an FNOD command is being completed under the incorrect Veteran’s record, then:   * select the ABORT MOD ONLY button (this will stop any payment and letters being issued), and * refer the case to adjudication using the MOD Memorandum found in Exhibit 1. |
| 7 | Select the UPDATE button on the VID screen. The MONTH OF DEATH screen will automatically appear. |
| 8 | Verify that the Veteran’s and spouse’s information on the MONTH OF DEATH screen is complete and accurate.  If not accurate, modify the information.    Was the Veteran buried in a State or national cemetery?   * If *yes*, leave the VET BURIED IN STATE OR NATIONAL CEMETERY box checked. * If *no*, uncheck the VET BURIED IN STATE OR NATIONAL CEMETERY box. |
| 9 | Select the applicable notice in the TYPE OF NOTICE drop-down menu.   * The following notices will *not* send contemporaneous notice to the Veteran:    + *DEATH CERTIFICATE/DEATH NOTICE*   + *DEATH BENEFIT CLAIM*   + *BURIAL BENEFIT/HEADSTONE/MARKER CLAIM*   + *FLAG APPLICATION*   + *INTERMENT RECORD*   + *NOTICE OF DEATH MESSAGE*, or   + *VA INSURANCE CLAIM*. * The following notices *will* send contemporaneous notice to the Veteran:    + *TELEPHONE FNOD*   + *PERSONAL INTERVIEW FNOD*   + *INSURANCE PCR FNOD*, or   + *DEATH MATCH*. |
| 10 | If the Veteran had *no* spouse or the spouse’s information is discrepant or incomplete, then check the SEND NEXT OF KIN LETTER box.    ***Note***: If a dependent spouse is not on the Veteran’s award, the MONTH OF DEATH screen will default to SEND NEXT OF KIN LETTER to the Veteran’s last known mailing address.  If the evidence shows that a surviving spouse exists, and entitlement to the Month of Death (MOD) payment is determined, add the surviving spouse on the MONTH OF DEATH screen by selecting the ADD NEW SPOUSE check box.  Then complete the surviving spouse’s information, including date of birth and SSN.  Once complete, select the UPDATE button. |
| 11 | Select the UPDATE button on the MONTH OF DEATH screen.  Confirmation that the MOD has been successfully submitted will appear.  Select the OK button.  The PRESIDENTIAL MEMORIAL CERTIFICATE screen will automatically appear.  If the requirements for the Presidential Memorial Certificate have not been met, do not create the Presidential Memorial Certificate.    ***Note***:  In order to release the MOD payment from the MONTH OF DEATH screen, it is required that the SSN is available at the time the FNOD command is completed.  If the spouse has no SSN, or the SSN is not available while performing the FNOD command, the MOD payment cannot be processed and the SEND NEXT OF KIN LETTER is the only option the user can select. |
| 12 | If there is a spouse of record in the system, this information will be pre-populated on the PRESIDENTIAL MEMORIAL CERTIFICATE screen. Verify that the information is complete and accurate.  If not, modify the information. |
| 13 | Select the CREATE CERTIFICATE button on the PRESIDENTIAL MEMORIAL CERTIFICATE screen. |
| 14 | If applicable, scan and upload the NOD mail into the Veteran’s eFolder.    ***Note***:  If a survivor claim was submitted with the NOD mail, then establish the appropriate EP with the correct claim attributes for proper National Work Queue routing. |

***Note***:  If the surviving spouse was receiving an apportionment, do *not* pay the MOD payment until the claims folder is reviewed to ensure there is no pending action to remove the spouse.

***References***:  For more information on

* MOD benefit, see [M21-1, Part XI, Subpart ii, 2](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174191/)
* Presidential Memorial Certificate entitlement and processing instructions, see

  + [M21-1, Part XI, Subpart iii, 1.D.1](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174203/), and
  + the *[Share User Guide](http://css.vba.va.gov/SHARE/)*
* the jurisdiction of in-service death claims, see [M21-1, Part II, Subpart ii, 3.1.b](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174868/), and
* in-service death claim labels for EP 130 and EP 140, see [M21-4, Appendix C](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000036570/).

---

**XI.i.1.B.2.b . Modifying Existing Dependent Spouse of Record on MONTH OF DEATH Screen**

Follow the steps in the table below when a dependent spouse's record should be modified.

| **Step** | **Action** |
| --- | --- |
| 1 | On the MONTH OF DEATH screen, select MODIFY EXISTING SPOUSE.    ***Note***:Check the ALL RELATIONSHIPS tab under the PERSON button for any existing spouse.  If there is a Y in the AWARD IND field, the spouse is currently included in the Veteran's award.  The Y indicator is also on the AWARD INFORMATION screen. |
| 2 | Complete the field under UPDATE SPOUSE INFORMATION and select the UPDATE button.    ***Note***: If the MONTH OF DEATH NOT PROCESSED, REASON IS: SSN OR FILE\_NBR ALREADY EXISTS - REFER MOD TO ADJUDICATION message appears, send the claim to adjudication for review. |
| 3 | Select the UPDATE button on the MONTH OF DEATH screen.  Confirmation that the MOD has been successfully submitted will appear.  Select the OK button.  The PRESIDENTIAL MEMORIAL CERTIFICATE screen will automatically appear.  If the requirements for the Presidential Memorial Certificate have not been met, do not create the Presidential Memorial Certificate. |

---

**XI.i.1.B.2.c . Identifying MOD Cases Paid by Batch**

Cases paid by the batch MOD process are completed under an EP 299 with the *Automated Month of Death Payment* claim label.

---

**XI.i.1.B.2.d . Amending the CPD Spouse Tab Created by the Automated MOD Process**

Following the automated FNOD/MOD processing, a claim for death benefits is often received from the surviving spouse.  The COMPENSATION AND PENSION DEATH (CPD) SPOUSE tab will exist in VMBS-Awards (VBMS-A) and the user will ***not*** need to add a new award.

Follow the steps in the table below when amending the CPD SPOUSE tab.

| **Step** | **Action** |
| --- | --- |
| 1 | Select the RECORD DECISIONS button. |
| 2 | Select the BASIC ELIGIBILITY tab.  This screen will show ELIGIBLE FOR VETERAN’S RATE MONTH OF DEATH in the DECISION field.  Do ***not*** remove this decision unless you are denying MOD. |
| 3 | Select the appropriate death benefit eligibility decision. |
| 4 | Input the appropriate date in the EVENT DATE field.    ***Note***:  The EFFECTIVE DATE field will automatically default to the first of the month following the event date. |
| 5 | Select the ACCEPT button and this will record the decision.    ***Note***:  The screen will display both decisions. |
| 6 | Select the OK button.  This will take the user to the RECORD DECISIONS screen.    Generate the award. |

---

**XI.i.1.B.2.e . Reviewing the ALL AWARDS Page for MOD Payments**

Follow the steps in the table below when reviewing a record in the ALL AWARDS page.

| **Step** | **Action** |
| --- | --- |
| 1 | Select the CPD SPOUSE tab. |
| 2 | Review the EFFECTIVE box for award information.    ***Note***:  If the ALL AWARDS page shows two tabs for the same spouse, it is possible that the surviving spouse received two MOD payments for two different Veterans.  Review the records to determine whether the surviving spouse is entitled to any of those MOD payments. |

---

**XI.i.1.B.2.f . Granting Entitlement to MOD Payment Only**

If it is determined that no MOD was previously paid by a one-time transaction in finance or the batch MOD process, the user can grant entitlement to the MOD payment only.

***Example***:  The MOD payment is rejected because the SSN was duplicated in our database.

Follow the steps in the table below to grant entitlement to MOD payment only.

| **Step** | **Action** |
| --- | --- |
| 1 | Establish an EP 290 – MOD – ENTITLEMENT REVIEW. |
| 2 | In the ALL AWARDS page, if a CPD SPOUSE tab is not already created, add a CPD SPOUSE tab by selecting the ADD NEW AWARD button, and choosing CPD SPOUSE in the drop-down AWARD TYPE menu. |
| 3 | Select the BASIC ELIGIBILITY tab and select the ADD button.  Select the RECORD DECISIONS button. |
| 4 | Select the BASIC ELIGIBILITY tab and select the ADD button. |
| 5 | Select ELIGIBILE FOR VETERAN’S RATE MONTH OF DEATH from the BASIC ELIGIBILITY tab. |
| 6 | Input the date in the EVENT DATE and the AWARD EFFECTIVE DATE field.    ***Note***:  The MOD effective date is the first day of the month of the Veteran’s death. |
| 7 | Input the amount in the MONTH OF DEATH AMOUNT field, which is the amount the Veteran was entitled to at the time of death. |
| 8 | Select the benefit from the BENEFIT drop-down menu. |
| 9 | Select the SERVICE PERIOD and the ACCEPT button.    The recorded decision will display, then select the OK button.    Generate the award. |

***Reference***:  For information on financial transactions, see the *Enterprise Management of Payments Workload and Reporting for VA (eMPWR-VA) User Guide*.

---

**XI.i.1.B.2.g . Denying Entitlement to MOD**

Follow the steps in the table below if it is determined that an MOD batch payment was released erroneously to the incorrect spouse and the MOD payment should be denied.

| **Step** | **Action** |
| --- | --- |
| 1 | Establish a claim under an EP 290. |
| 2 | Select the RECORD DECISIONS button. |
| 3 | Select the BASIC ELIGIBILITY tab.    ***Note***:  This screen will show ELIGIBLE FOR VETERAN’S RATE MONTH OF DEATH in the DECISION box. |
| 4 | Select the EDIT button.    ***Note***:  This will enable the BASIC ELIGIBILITY DECISION fields for editing. |
| 5 | Chose one of the two MOD denial reasons:   * DENIED-VETERAN’S MOD RATE PREVIOUSLY PAID, or * DENIED – NOT ENTITLED TO MOD.   This will replace the prior decision automatically inserted by the batch MOD process. |
| 6 | Generate the award.    ***Note***:  If a user adds a second decision denying MOD entitlement under the BASIC ELIGIBILITY tab, this action will ***not*** create an overpayment on the surviving spouse’s account. |

---

**XI.i.1.B.2.h . When the System Finds Multiple Records During the NOD Processing**

When the system finds multiple records during NOD processing, use the table below to determine how to

* review a BIRLS record, or
* return to the BIRLS SELECTION screen.

| **If you want to …** | **Then …** |
| --- | --- |
| review a BIRLS record | * *double click* the BIRLS record, or * select the BIRLS record and then use the INQUIRY command. |
| return to the BIRLS SELECTION screen | use the SELECTION command. |

---

**XI.i.1.B.2.i . Disposition of Veteran NOD Data Prints**

The system generates a Veteran NOD VID screen print when NOD processing results in a

* new BIRLS record, or
* NOD folder in BIRLS.

These prints should be destroyed in accordance with *[VBA Letter 20-08-63, VBA Policy on Management of Veterans' and other Governmental Paper Records](https://vbaw.vba.va.gov/USB/2008.asp)*.

---

**XI.i.1.B.2.j . Assigning New File Numbers During the Veteran NOD Processing**

Use the table below when assigning a new file number during the Veteran NOD process.

| **Step** | **Action** |
| --- | --- |
| 1 | Select the FNOD command on the VBA READY screen, and enter the following minimum required information about the Veteran:   * file number or SSN * first name, middle name or initial, and last name, and * date of birth. |
| 2 | If the minimum required information is in the system, but the BIRLS database search fails to locate an existing record, establish a new BIRLS record and proceed with the NOD steps in [M21-1, Part XI, Subpart i, 1.B.2.a](#2a).    ***Important***:  Use extreme care not to add a new BIRLS record until *all* searches for a current BIRLS record to include name variations have been completed. |
| 3 | If the minimum required information is *not* available and the BIRLS database search fails to locate an existing record   * terminate FNOD processing, and * write to the claimant or next of kin for additional identifying information.   ***Note***:  If the NOD is a claim form, advise the claimant to respond within 30 days or the Department of Veterans Affairs (VA) cannot take action.  If you receive a response but the claimant or next of kin cannot provide the Veteran’s service number or SSN, send *[VA Form 21-3101, Request for Information](https://vbaw.vba.va.gov/bl/20/cio/20s5/forms/VBA-21-3101-ARE.pdf)*, to the appropriate service department.  Do not use the Personnel Information Exchange System to send *[VA Form 21-3101](https://vbaw.vba.va.gov/bl/20/cio/20s5/forms/VBA-21-3101-ARE.pdf)* since there is no assigned file number. |

---

##

## 3.  Processing MOD Payments With Other Death Benefits

---

**Introduction**

This topic contains information on processing MOD payments along with other death benefits, including

* [spouse receiving an apportionment at the time the FNOD command is performed](#3a)
* [entitlement to Dependency and Indemnity Compensation (DIC) and MOD with no running award](#3b)
* [entitlement to MOD with DIC or Survivors Pension already running,](#3c) and
* [amending a running spouse award after MOD has been paid by finance action, interim MOD process, or retro batch MOD](#3d).

---

**Change Date**

February 14, 2025

---

**XI.i.1.B.3.a . Spouse Receiving an Apportionment at the Time the FNOD Command Is Performed**

If a surviving spouse is receiving an apportionment at the time the FNOD command is performed, the corporate record will reflect both award types for payee 10 (primary and apportionee).

After the MOD payment is released, the CPD Spouse award will reflect the payment released to the surviving spouse and the debt created on the apportionment account.

***Reference***:  For information on financial transactions, see the *eMPWR-VA User Guide*.

---

**XI.i.1.B.3.b . Entitlement to DIC and MOD With No Running Award**

Follow the steps in the table below when there is entitlement to Dependency and Indemnity Compensation (DIC) and MOD and there is no running award.

| **Step** | **Action** |
| --- | --- |
| 1 | On the VBMS-A ALL AWARDS page, select ADD NEW AWARD, then select *CPD SPOUSE* from the AWARD TYPE drop-down menu (if a CPD SPOUSE tab is not already created). |
| 2 | Select the RECORD DECISIONS button. |
| 3 | Select the RATING tab. |
| 4 | Select the DEATH DECISIONS tab.    ***Note***:  A rating decision is needed, if this screen is blank, and the Veteran did not die in service. |
| 5 | Under the BASIC ELIGIBILITY tab, select the ADD button. |
| 6 | Select the appropriate DIC eligibility reason. |
| 7 | Input the date in the EVENT DATE field.    ***Note***:  The EFFECTIVE DATE field will automatically default to the first day of the month following the event date. |
| 8 | Select the ACCEPT button.  This will record the DIC decision. |
| 9 | Select the ADD button to record the MOD decision. |
| 10 | Select *ELIGIBLE FOR VETERAN’S RATE MONTH OF DEATH* from the BASIC ELIGIBILITY drop-down menu. |
| 11 | Input the date in the EVENT DATE and AWARD EFFECTIVE DATE field.    ***Note***:  The MOD effective date is the first day of the month of the Veteran’s death. |
| 12 | Select the benefit from the BENEFIT drop-down menu. |
| 13 | Select the SERVICE PERIOD field. |
| 14 | Click the ACCEPT button.  The screen will display both decisions. |
| 15 | Select the OK button.  This will take the user to the RECORD DECISIONS screen. |
| 16 | Generate the award. |

---

**XI.i.1.B.3.c . Entitlement to MOD With DIC or Survivors Pension Already Running**

If the user is granting MOD entitlement to a surviving spouse that already has a DIC or Survivors Pension award running, leave the DIC or Survivors Pension decision under the BASIC ELIGIBILITY tab and add the new MOD decision.  Follow the steps in the table below to process the award in this situation.

| **Step** | **Action** |
| --- | --- |
| 1 | Select *Eligible for Veteran’s Rate Month of Death* from the DECISIONS drop-down menu on the BASIC ELIGIBILITY screen. |
| 2 | Input the date in the EVENT DATE and AWARD EFFECTIVE DATE field.    ***Note***:  The MOD effective date is the first day of the month of the Veteran’s death. |
| 3 | Input the amount in the MONTH OF DEATH AMOUNT field.    ***Note***:  This is the amount the Veteran was entitled to at the time of death. |
| 4 | Select the benefit from the BENEFIT drop-down menu. |
| 5 | Select the SERVICE PERIOD field. |
| 6 | Click the ACCEPT button.  The screen will display both decisions. |
| 7 | Select the OK button.    ***Note***:  This will take the user to the RECORD DECISIONS screen. |
| 8 | Generate the award.    ***Note***:  The AWARD INFORMATION tab will now contain the previous award information (that is, Original Award) and “Entitled to MOD Benefit.” |

---

**XI.i.1.B.3.d . Amending a Running Spouse Award After MOD Has Been Paid by Finance Action, Interim MOD Process, or Retro Batch MOD**

A running award or a converted record will likely have had the MOD paid via an old method.  These cases will not have an MOD decision in the VBMS-A record unless it was paid on the award itself.

Effective August 2010, all DIC and Survivors Pension cases require an MOD decision.  Otherwise, the error message SURVIVING SPOUSE AWARD REQUIRES A MONTH OF DEATH DECISION will appear.

Follow the steps in the table below to amend a running surviving spouse award after MOD has been paid by finance action, interim MOD process, or retro batch MOD.

| **Step** | **Action** |
| --- | --- |
| 1 | The surviving spouse’s death benefit decision(s) will be displayed on the BASIC ELIGIBILITY screen. |
| 2 | Select ADD and then select the *Denied – Veteran’s MOD Rate Previously Paid* option from the DECISION drop-down menu. |
| 3 | Select DONE.    This will take the user to the RECORD DECISIONS screen.    ***Note***:  If it is a converted case, the user must input a date on the ONLY GENERATE NEW AWARD LINES FROM field. |
| 4 | Generate the award. |

---

## **4**.**** Exhibit 1:  MOD Memorandum

---

**Change Date**

January 20, 2016

---

**XI.i.1.B.5.a . MOD Memorandum**

This exhibit contains an example of an MOD Memorandum sent to adjudication.

**Memorandum**

**MOD Failure Referred to \_\_\_\_\_\_\_\_\_\_\_\_\_  Date \_\_\_\_\_\_\_\_\_\_\_\_**

**While performing the Veteran’s FNOD, the following error appeared; therefore, we are referring the case to your Regional Office.**

|  |  |
| --- | --- |
| File Number |  |
| Veteran's SSN |
| Veteran's Name |
| Date of Death |
| Source of Notification |  |

|  |  |  |
| --- | --- | --- |
| **MOD UPDATE:  Month of Death not processed, reason is: (error number)** | **Reason** | **Selection** |
| 01 | Invalid Transaction |  |
| 02 | Update of spouse information failed |  |
| 03 | Invalid Transaction |  |
| 04 | Failed to create or updated MOD control record |  |
| 05 | Death Date is Null. FNOD needs to be performed |  |
| 06 | MOD transaction is already pending |  |
| 07 | SSN or File\_nbr Already Exists |  |
| 08 | Cannot Change SSN when SSN = Filenbr |  |
| 09 | Cannot Delete or Change Verified SSN |  |
| Aborted | First Notice of Death (FNOD) process under incorrect Veteran |  |

---

 [<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174187/)  [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174195/)

[To Top](#top)
