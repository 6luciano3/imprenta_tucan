# Strategy Pattern for unit conversion

class ConversionStrategy:
    def convert(self, value, from_unit, to_unit):
        raise NotImplementedError()


class SimpleConversionStrategy(ConversionStrategy):
    # Example: conversion rates can be loaded from DB or config
    conversion_rates = {
        ('cm', 'm'): lambda x: x / 100,
        ('m', 'cm'): lambda x: x * 100,
        ('kg', 'g'): lambda x: x * 1000,
        ('g', 'kg'): lambda x: x / 1000,
    }

    def convert(self, value, from_unit, to_unit):
        key = (from_unit, to_unit)
        if key in self.conversion_rates:
            return self.conversion_rates[key](value)
        if from_unit == to_unit:
            return value
        raise ValueError(f"No conversion strategy for {from_unit} -> {to_unit}")
