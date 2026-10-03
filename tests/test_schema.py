import unittest

from praetor.security.schema import ValidationError, validate_arguments, validate_schema

SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "count": {"type": "integer", "enum": [1, 2, 3]},
    },
    "required": ["path"],
}


class SchemaTests(unittest.TestCase):
    def test_accepts_valid_arguments(self):
        validate_arguments(SCHEMA, {"path": "a.txt", "count": 2})

    def test_rejects_unknown_argument(self):
        with self.assertRaises(ValidationError):
            validate_arguments(SCHEMA, {"path": "a", "evil": 1})

    def test_rejects_missing_required(self):
        with self.assertRaises(ValidationError):
            validate_arguments(SCHEMA, {"count": 1})

    def test_rejects_wrong_type(self):
        with self.assertRaises(ValidationError):
            validate_arguments(SCHEMA, {"path": 5})

    def test_rejects_bool_as_integer(self):
        with self.assertRaises(ValidationError):
            validate_arguments(SCHEMA, {"path": "a", "count": True})

    def test_rejects_bad_enum_value(self):
        with self.assertRaises(ValidationError):
            validate_arguments(SCHEMA, {"path": "a", "count": 9})

    def test_rejects_malformed_schema(self):
        with self.assertRaises(ValidationError):
            validate_schema({"type": "object"})


if __name__ == "__main__":
    unittest.main()
