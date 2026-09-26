"""Ten independent Click default/type contracts, with no pytest or network."""
import unittest
import click
from click.testing import CliRunner


class DefaultContract(unittest.TestCase):
    def invoke(self, option, args=(), **kwargs):
        command = click.Command('sample',params=[option],callback=lambda **values: values[option.name])
        result = CliRunner().invoke(command,list(args),standalone_mode=False,**kwargs)
        self.assertIsNone(result.exception,str(result.exception))
        return result.return_value

    def test_repeated_scalar_issue_reproduction(self):
        option=click.Option(['--count'],multiple=True,default=(2,5))
        self.assertEqual(option.nargs,1)
        self.assertIs(option.type,click.INT)
        self.assertEqual(self.invoke(option),(2,5))

    def test_list_and_string_scalar_defaults(self):
        for default,expected in [([3,7],(3,7)),(('north','south'),('north','south'))]:
            with self.subTest(default=default):
                option=click.Option(['--value'],multiple=True,default=default)
                self.assertEqual(option.nargs,1)
                self.assertEqual(self.invoke(option),expected)

    def test_composite_default_inference(self):
        option=click.Option(['--pair'],multiple=True,default=[(1,'north'),(3,'south')])
        self.assertEqual(option.nargs,2)
        self.assertIsInstance(option.type,click.Tuple)
        self.assertEqual(option.type.types,[click.INT,click.STRING])
        self.assertEqual(self.invoke(option),((1,'north'),(3,'south')))

    def test_scalar_command_line_overrides_default(self):
        option=click.Option(['--count'],multiple=True,default=(2,5))
        self.assertEqual(self.invoke(option,['--count','8','--count','9']),(8,9))

    def test_composite_command_line_overrides_default(self):
        option=click.Option(['--pair'],multiple=True,default=[(1,'north')])
        self.assertEqual(self.invoke(option,['--pair','4','west','--pair','5','east']),((4,'west'),(5,'east')))

    def test_missing_defaults_and_optional_nargs(self):
        cases=[({'multiple':True},()),({'nargs':2},None),({'nargs':2,'multiple':True},())]
        for settings,expected in cases:
            with self.subTest(settings=settings):
                option=click.Option(['--value'],default=None,**settings)
                self.assertEqual(self.invoke(option),expected)

    def test_explicit_composite_type_casts_default(self):
        option=click.Option(['--pair'],type=(int,str),multiple=True,default=[('2','east')])
        self.assertEqual(self.invoke(option),((2,'east'),))

    def test_bad_numeric_input_is_usage_error(self):
        option=click.Option(['--count'],multiple=True,default=(2,5))
        command=click.Command('sample',params=[option],callback=lambda **values: values)
        result=CliRunner().invoke(command,['--count','not-an-integer'])
        self.assertEqual(result.exit_code,2)
        self.assertIn('Invalid value',result.output)
        self.assertIn('--count',result.output)

    def test_default_map_precedence_and_casting(self):
        option=click.Option(['--count'],multiple=True,default=(2,5))
        self.assertEqual(self.invoke(option,default_map={'count':['8','9']}),(8,9))

    def test_environment_precedence_and_casting(self):
        option=click.Option(['--count'],multiple=True,default=(2,5),envvar='TRACEPATCH_COUNTS')
        self.assertEqual(self.invoke(option,env={'TRACEPATCH_COUNTS':'8 9'}),(8,9))
        self.assertEqual(self.invoke(option,['--count','6'],env={'TRACEPATCH_COUNTS':'8 9'}),(6,))


if __name__=='__main__':
    unittest.main(verbosity=2)
