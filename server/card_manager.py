import json
import argparse

AUTH_CARDS_FILE = 'authorized_cards.json'
LOG_FILE = 'access_log.json'

def load_cards():
    try:
        with open(AUTH_CARDS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"cards": []}

def save_cards(data):
    with open(AUTH_CARDS_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Dados do cartão salvos em {AUTH_CARDS_FILE}")

def list_cards():
    card_data = load_cards()
    print("\n--- Cartões Autorizados ---")
    print(f"{'ID do Cartão':<15} {'Nome':<20} {'Status':<10}")
    print("-" * 45)
    for card in card_data.get("cards", []):
        status = "Autorizado" if card.get("authorized") else "Negado"
        print(f"{card.get('id'):<15} {card.get('name'):<20} {status:<10}")

def add_card(card_id, name, authorized=True):
    card_data = load_cards()
    
    # Verifica se o cartão já existe
    for card in card_data.get("cards", []):
        if card.get("id") == card_id:
            print(f"Cartão {card_id} já existe!")
            return

    # Adicionar novo cartão
    new_card = {
        "id": card_id,
        "name": name,
        "authorized": authorized
    }
    card_data["cards"].append(new_card)
    save_cards(card_data)
    print(f"Cartão adicionado: {card_id} - {name} ({'Autorizado' if authorized else 'Negado'})")

def delete_card(card_id):
    card_data = load_cards()
    initial_count = len(card_data.get("cards", []))
    
    card_data["cards"] = [card for card in card_data.get("cards", []) 
                         if card.get("id") != card_id]
    
    if len(card_data.get("cards", [])) < initial_count:
        save_cards(card_data)
        print(f"Cartão excluído: {card_id}")
    else:
        print(f"Cartão {card_id} não encontrado!")

def update_card(card_id, authorized):
    card_data = load_cards()
    found = False
    
    for card in card_data.get("cards", []):
        if card.get("id") == card_id:
            card["authorized"] = authorized
            found = True
            break
    
    if found:
        save_cards(card_data)
        print(f"Cartão atualizado {card_id}: {'Autorizado' if authorized else 'Negado'}")
    else:
        print(f"Cartão {card_id} não encontrado!")

def show_logs():
    try:
        with open(LOG_FILE, 'r') as f:
            logs = json.load(f)
        
        print("\n--- Registros de Acesso ---")
        print(f"{'Data/Hora':<25} {'ID do Cartão':<15} {'Status':<10}")
        print("-" * 50)
        for entry in logs:
            status = "Autorizado" if entry.get("authorized") else "Negado"
            print(f"{entry.get('timestamp'):<25} {entry.get('card_id'):<15} {status:<10}")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Nenhum registro de acesso disponível.")

def main():
    parser = argparse.ArgumentParser(description='Ferramenta de Gerenciamento de Cartões RFID')
    subparsers = parser.add_subparsers(dest='command', help='Comandos')
    
    # Comando para listar cartões
    subparsers.add_parser('list', help='Listar todos os cartões')
    
    # Comando para adicionar cartão
    add_parser = subparsers.add_parser('add', help='Adicionar um novo cartão')
    add_parser.add_argument('card_id', help='ID do cartão (ex: 0x1a2b3c4d)')
    add_parser.add_argument('name', help='Nome associado ao cartão')
    add_parser.add_argument('--deny', action='store_true', help='Adicionar como negado (não autorizado)')
    
    # Comando para excluir cartão
    delete_parser = subparsers.add_parser('delete', help='Excluir um cartão')
    delete_parser.add_argument('card_id', help='ID do cartão a ser excluído')
    
    # Comando para atualizar cartão
    update_parser = subparsers.add_parser('update', help='Atualizar autorização do cartão')
    update_parser.add_argument('card_id', help='ID do cartão a ser atualizado')
    update_parser.add_argument('--authorize', action='store_true', help='Autorizar o cartão')
    update_parser.add_argument('--deny', action='store_true', help='Negar o cartão')
    
    # Comando para mostrar registros
    subparsers.add_parser('logs', help='Mostrar registros de acesso')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_cards()
    elif args.command == 'add':
        add_card(args.card_id, args.name, not args.deny)
    elif args.command == 'delete':
        delete_card(args.card_id)
    elif args.command == 'update':
        if args.authorize and args.deny:
            print("Erro: Não é possível autorizar e negar simultaneamente")
        elif args.authorize:
            update_card(args.card_id, True)
        elif args.deny:
            update_card(args.card_id, False)
        else:
            print("Erro: Deve especificar --authorize ou --deny")
    elif args.command == 'logs':
        show_logs()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
