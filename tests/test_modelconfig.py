import unittest
from tracepatch.modelconfig import select_profile


class ModelConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = {'model': 'old', 'base_url': 'https://example.invalid/v1', 'first_run_budget_cny': 85,
                       'pricing': {'input': 1, 'output': 2}}
        self.profiles = {'coder': {'model': 'coder', 'pricing': {'currency': 'CNY', 'unit_tokens': 1000000,
                                                             'source': 'test quote', 'input': 4.75, 'output': 19}}}

    def test_default_does_not_change_existing_configuration(self):
        selected = select_profile(self.config, self.profiles)
        self.assertEqual(selected, self.config)
        selected['pricing']['input'] = 9
        self.assertEqual(self.config['pricing']['input'], 1)

    def test_model_and_quote_are_selected_together(self):
        selected = select_profile(self.config, self.profiles, 'coder')
        self.assertEqual(selected['model'], 'coder')
        self.assertEqual(selected['pricing']['output'], 19)
        self.assertEqual(selected['base_url'], self.config['base_url'])
        self.assertEqual(selected['first_run_budget_cny'], 85)
        selected['pricing']['input'] = 9
        self.assertEqual(self.profiles['coder']['pricing']['input'], 4.75)

    def test_unknown_profile_and_provider_override_rejected(self):
        with self.assertRaises(ValueError):
            select_profile(self.config, self.profiles, 'typo')
        self.profiles['coder']['base_url'] = 'https://elsewhere.invalid'
        with self.assertRaises(ValueError):
            select_profile(self.config, self.profiles, 'coder')

    def test_invalid_price_or_units_rejected(self):
        for bad in (True, -1, float('nan'), float('inf'), '4.75', None):
            with self.subTest(bad=bad):
                self.profiles['coder']['pricing']['input'] = bad
                with self.assertRaises(ValueError):
                    select_profile(self.config, self.profiles, 'coder')
        self.profiles['coder']['pricing'].update(input=4.75, unit_tokens=1000)
        with self.assertRaises(ValueError):
            select_profile(self.config, self.profiles, 'coder')
