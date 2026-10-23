import unittest

from aic_connector.adapters import AdapterRegistry, ConnectorManifest


class FakeAdapter:
    def __init__(self, manifest):
        self.manifest = manifest

    def status(self, *, subject=None):
        return {"connected": False, "subject": subject}


def manifest(connector_id="facebook", actions=("facebook.pages.list", "facebook.post.prepare")):
    return ConnectorManifest(
        connector_id=connector_id,
        display_name=connector_id.title(),
        auth_mode="oauth2",
        required_scopes=("pages_show_list",),
        supported_actions=actions,
    )


class ConnectorManifestTests(unittest.TestCase):
    def test_rejects_invalid_connector_id(self):
        with self.assertRaisesRegex(ValueError, "connector_id_invalid"):
            manifest("../facebook")

    def test_rejects_action_from_another_connector(self):
        with self.assertRaisesRegex(ValueError, "action_connector_prefix_mismatch"):
            manifest(actions=("gmail.search",))

    def test_rejects_duplicate_scopes(self):
        with self.assertRaisesRegex(ValueError, "duplicate_scope"):
            ConnectorManifest(
                connector_id="facebook",
                display_name="Facebook",
                auth_mode="oauth2",
                required_scopes=("pages_show_list", "pages_show_list"),
                supported_actions=("facebook.pages.list",),
            )


class AdapterRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = AdapterRegistry()
        self.facebook = FakeAdapter(manifest())
        self.registry.register(self.facebook)

    def test_resolves_only_registered_actions(self):
        self.assertIs(self.registry.resolve_action("facebook.pages.list"), self.facebook)
        self.assertIsNone(self.registry.resolve_action("facebook.post.publish"))
        self.assertIsNone(self.registry.resolve_action("gmail.search"))

    def test_duplicate_connector_registration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "connector_id_already_registered"):
            self.registry.register(FakeAdapter(manifest()))

    def test_manifest_output_contains_no_credentials(self):
        result = self.registry.list_manifests()
        self.assertEqual(result[0]["auth_mode"], "oauth2")
        self.assertNotIn("token", str(result).lower())
        self.assertEqual(result[0]["supported_actions"], ["facebook.pages.list", "facebook.post.prepare"])

    def test_registry_does_not_claim_connection(self):
        self.assertEqual(self.facebook.status()["connected"], False)
        self.assertEqual(len(self.registry), 1)


if __name__ == "__main__":
    unittest.main()
