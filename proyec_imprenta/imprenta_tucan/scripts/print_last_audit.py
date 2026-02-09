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
        from auditoria.models import AuditEntry
        print('Total audit entries:', AuditEntry.objects.count())
        qs = AuditEntry.objects.order_by('-timestamp')[:20]
        if not qs:
            print('No audit entries found')
            return
        for ae in qs:
            print('---')
            print('Object ID:', ae.object_id)
            print('Model:', ae.model)
            print('App:', ae.app_label)
            print('Action:', ae.action)
            print('Path:', ae.path)
            print('Changes:', (ae.changes or '')[:300])
            print('Extra:', (ae.extra or '')[:300])
    except Exception as e:
        print(f"Error reading audit: {e}")


if __name__ == '__main__':
    main()
