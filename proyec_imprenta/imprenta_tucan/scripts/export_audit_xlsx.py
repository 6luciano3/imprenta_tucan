import os
import sys


def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(os.path.abspath(os.path.join(project_root, '..')))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
    try:
        import django
        django.setup()
    except Exception as e:
        print(f"Failed to setup Django: {e}")
        return

    try:
        from django.test import RequestFactory
        from auditoria.views import exportar_auditoria_xlsx

        rf = RequestFactory()
        # You can change params below to filter
        req = rf.get('/auditoria/exportar-xlsx/?categoria=stock-movement')
        resp = exportar_auditoria_xlsx(req)
        out_path = os.path.abspath(os.path.join(project_root, '..', 'auditoria_test.xlsx'))
        with open(out_path, 'wb') as f:
            f.write(resp.content)
        print(f"Wrote: {out_path} ({len(resp.content)} bytes)")
    except Exception as e:
        print(f"Error exporting audit XLSX: {e}")


if __name__ == '__main__':
    main()
