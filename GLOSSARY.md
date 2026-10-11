# Lidl Engine

Lidl Engine helps its owner find Lidl offers for a planned shopping date and understand the conditions of each advertised deal.

## Language

**Flyer**:
A digital leaflet published by Lidl containing advertised products and deals. A regular flyer is presented as `Gazetka` in the Lidl Poland listing.
_Avoid_: Catalog when referring to a regular flyer

**Current flyer**:
The first regular `Gazetka` in the latest successfully discovered Lidl Poland listing. Its selection does not establish that every advertised offer is valid on the shopping date.
_Avoid_: Latest fully processed flyer

**Source page**:
A page of a flyer containing the advertisement from which offer details were collected.
_Avoid_: Product page

**Offer**:
An advertised grocery product or group of products with a stated price or purchase benefit. An offer can advertise an ordinary price without claiming a discount.
_Avoid_: Product, discount when referring to every offer

**Offer occurrence**:
An advertisement of an offer on one source page. One offer can have multiple occurrences when repeated advertisements agree on its subject, validity, price, and purchase conditions.
_Avoid_: Separate offer for every repeated advertisement

**Conflicting variants**:
Advertisements that appear to describe the same deal but disagree on its price or purchase conditions. They remain distinct offers with their source details and are presented together.
_Avoid_: Ordinary and coupon deals when those genuinely have different terms

**Conflict context**:
A conflicting variant shown alongside a matching offer to expose a source disagreement, even when that variant does not match the selected filters. Its presence does not establish validity on the shopping date.
_Avoid_: Matching offer, valid offer when the variant is shown only for context

**Shopping date**:
The calendar day for which the owner wants to find applicable offers.
_Avoid_: Scrape date, flyer date

**Offer category**:
A grouping based on the type of product an offer concerns, such as bakery or vegetables.
_Avoid_: Promotion mechanism, offer type

**Pantry items**:
Groceries kept for later preparation or use, including tea and coffee sold for brewing. Tea and coffee sold as ready-to-drink products belong to non-alcoholic beverages.
_Avoid_: Panty items

**Purchase conditions**:
The requirements for obtaining an advertised price or benefit, such as buying a specified quantity, using Lidl Plus, or activating a coupon. Purchase limits describe how much of the deal a shopper can receive.
_Avoid_: Discount when referring to requirements

**Inferred validity bound**:
An offer's start or end date taken from the advertised flyer period because that date is absent from the offer itself.
_Avoid_: Explicit offer date

**Unknown validity**:
An offer whose start or end date remains unsupported after available flyer dates are considered. Any known bound still constrains when the offer can apply.
_Avoid_: Always valid

**Unknown detail**:
An offer detail for which the available source provides no supported value. An unknown requirement does not establish that the requirement is absent.
_Avoid_: Not required when the requirement is unstated

**Stated price**:
A price amount advertised for a particular quantity or unit, together with any applicable purchase conditions. It does not establish an effective multibuy price or include an unstated deposit.
_Avoid_: Universal price, calculated deal price
