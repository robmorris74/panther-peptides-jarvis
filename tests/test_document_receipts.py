import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app223 import business, db

class DocumentReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patch=patch.object(db,'DB_PATH',Path(self.temp.name)/'test.db')
        self.patch.start()
        business.ensure_business_schema()
        self.lot=db.execute("INSERT INTO pp_inventory(product,lot_code,status,coa_status,quantity) VALUES('Test','B-1','quarantine','missing',10)")
    def tearDown(self):
        self.patch.stop();self.temp.cleanup()
    def test_receipts_persist_without_review_or_release(self):
        for kind in business.DOCUMENT_RECEIPT_KINDS:
            business.record_document_receipt(self.lot,kind,True,'Report ABC')
        row=business.inventory_rows()[0]
        self.assertEqual(len(row['receipts']),3)
        self.assertTrue(all(x['received']==1 and x['recorded_by']=='owner' for x in row['receipts']))
        self.assertEqual((row['status'],row['coa_status'],row['documents']),('quarantine','missing',[]))
        business.record_document_receipt(self.lot,'coa',False,'Report ABC withdrawn')
        self.assertEqual(db.one("SELECT received FROM pp_document_receipts WHERE kind='coa'")['received'],0)
        self.assertEqual(len(business.events()),4)
    def test_invalid_receipts_do_not_mutate(self):
        for args in [(self.lot,'other',True,'ABC'),(self.lot,'coa',True,' '),(self.lot+1,'coa',True,'ABC')]:
            with self.assertRaises(ValueError):business.record_document_receipt(*args)
        self.assertEqual(db.execute('SELECT * FROM pp_document_receipts',fetch=True),[])

if __name__=='__main__':unittest.main()
