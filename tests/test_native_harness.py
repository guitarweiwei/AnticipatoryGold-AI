"""Structural safeguards only. These checks do not compile or run the MQL script."""
import json
from pathlib import Path
import re
import unittest

from test_ea_safety import function_body, uncomment


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "MQL5/Tests/Native"


class NativeHarnessStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (NATIVE / "AnticipatoryGold_NativeTests.mq5").read_text()
        cls.code = uncomment(cls.source)

    def test_case_manifest_exact_unique_and_no_execution_results(self):
        expected = json.loads((NATIVE / "expected_cases.json").read_text())
        actual = re.findall(r'NativeCase\("([A-Z0-9_]+)"', self.code)
        self.assertGreater(len(actual), 0)
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(actual, expected["case_ids"])
        self.assertNotIn("passed", expected)
        self.assertNotIn("results", expected)

    def test_includes_production_with_all_events_renamed(self):
        include = self.code.index('#include "../../Experts/AnticipatoryGold_AI_v1.mq5"')
        for event in ("OnInit", "OnTick", "OnDeinit"):
            self.assertLess(self.code.index(f"#define {event} AGNativeProduction{event}"), include)
            self.assertGreater(self.code.index(f"#undef {event}"), include)
        self.assertNotRegex(function_body(self.code, "OnStart"), r'\b(?:AGNativeProduction\w+|OpenPosition|CloseAll|InitRiskState)\s*\(')

    def test_sender_adapters_do_not_delegate_to_real_sender(self):
        for name in ("AGNativeOrderSendBlocked", "AGNativeOrderSendAsyncBlocked"):
            body = function_body(self.code, name)
            self.assertNotRegex(body, r'\b(?:OrderSend|OrderSendAsync)\s*\(')
        self.assertIn("g_nativeSendAttempts++", function_body(self.code, "AGNativeOrderSendBlocked"))
        self.assertIn("return false;", function_body(self.code, "AGNativeOrderSendBlocked"))
        self.assertIn("#define OrderSend AGNativeOrderSendBlocked", self.code)
        self.assertIn("#define OrderSendAsync AGNativeOrderSendAsyncBlocked", self.code)

    def test_io_adapter_restricts_prefix_and_avoids_common_config(self):
        adapter = function_body(self.code, "AGNativeFileOpen")
        self.assertIn('StringFind(name,g_nativePrefix)!=0', adapter)
        self.assertIn('flags&=~FILE_COMMON', adapter)
        self.assertIn('return INVALID_HANDLE;', adapter)
        self.assertIn('StringFind(name,g_nativePrefix)!=0', function_body(self.code, "NativeWrite"))
        self.assertNotRegex(self.code, r'\b(?:FileDelete|WebRequest|SocketCreate|DLLImport)\s*\(')

    def test_results_distinguish_native_fixtures_and_missing_broker_evidence(self):
        self.assertIn('NATIVE-FILE-MOCKSTATE', self.source)
        self.assertIn('reload_not_process_restart_no_broker_order', self.source)
        self.assertIn('no_WebRequest_no_timeout_simulation', self.source)
        summary = function_body(self.code, "NativeSummary")
        self.assertIn('broker_fault_tests', summary)
        self.assertIn('performance_backtest', summary)
        self.assertIn('NOT_RUN', summary)
        case = function_body(self.code, "NativeCase")
        self.assertIn('\\"id\\"', case)
        self.assertIn('\\"passed\\"', case)


if __name__ == "__main__":
    unittest.main()
