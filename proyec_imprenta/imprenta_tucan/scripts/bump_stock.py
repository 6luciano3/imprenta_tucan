import os
import sys


def main():
    # Configure Django settings
    project_root = os.path.dirname(os.path.abspath(__file__))
    # Ensure we can import the Django project package (proyec_imprenta/imprenta_tucan)
    sys.path.append(os.path.abspath(os.path.join(project_root, '..')))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'impre_tucan.settings')
    try:
        import django
        django.setup()
    except Exception as e:
        print(f"Failed to setup Django: {e}")
        return

    try:
        from insumos.models import Insumo
        i = Insumo.objects.order_by('idInsumo').first()
        if not i:
            print('No Insumo found')
            return
        before = int(i.stock or 0)
        i.stock = before + 3
        i.save(update_fields=["stock", "updated_at"]) if hasattr(i, "updated_at") else i.save()
        print(f"Changed stock for Insumo {i.idInsumo} from {before} to {i.stock}")
    except Exception as e:
        print(f"Error bumping stock: {e}")


if __name__ == '__main__':
    main()
