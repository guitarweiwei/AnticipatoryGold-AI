import unittest
from acquire_frozen import can_resume
class RecoveryChecks(unittest.TestCase):
 def record(self,status='HTTP_ERROR',code=503,error='HTTP Error 503'):return {'status':status,'http_status':code,'error':error}
 def report(self,items):return {'files':items,'expected_hours':10248}
 def test_only_small_transient_failures_may_resume(self):self.assertTrue(can_resume(self.report([self.record(),self.record('DOWNLOAD_OR_DECODE_ERROR',None,'TimeoutError: timed out')])))
 def test_incomplete_http200_body_timeout_can_resume(self):self.assertTrue(can_resume(self.report([self.record('DOWNLOAD_OR_DECODE_ERROR',200,'TimeoutError: body timed out')])))
 def test_rate_limits_and_missing_hours_never_auto_resume(self):
  for rec in [self.record('ACCESS_OR_RATE_LIMIT_STOP',429),self.record('NOT_FOUND_UNCLASSIFIED',404)]:self.assertFalse(can_resume(self.report([rec])))
 def test_decode_failure_with_http200_never_auto_resumes(self):self.assertFalse(can_resume(self.report([self.record('DOWNLOAD_OR_DECODE_ERROR',200,'LZMAError: corrupt stream')])))
 def test_large_network_failure_set_stops(self):self.assertFalse(can_resume(self.report([self.record()]*600)))
 def test_success_does_not_trigger_second_pass(self):self.assertFalse(can_resume(self.report([self.record('DOWNLOADED',200,None)])))
if __name__=='__main__':unittest.main()
