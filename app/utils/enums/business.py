import enum


class IndustryCategory(str, enum.Enum):
    FASHION_APPAREL = "fashion_apparel"
    SKINCARE_BEAUTY = "skincare_beauty"
    GROCERIES_FOOD = "groceries_food"
    ELECTRONICS_RETAIL = "electronics_retail"
    REAL_ESTATE = "real_estate"
    PROFESSIONAL_SERVICES = "professional_services"
