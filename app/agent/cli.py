import argparse 
 
from app.agent.llm_agent import MetadataAgent 
from app.db import SessionLocal 
 
 
def main(): 
    parser = argparse.ArgumentParser(description='Metadata governance agent CLI') 
    parser.add_argument('question', type=str, help='Natural language question') 
    args = parser.parse_args() 
 
    db = SessionLocal() 
    try: 
        agent = MetadataAgent(db) 
        result = agent.ask(args.question) 
        print(result['answer']) 
        print('--- tool trace ---') 
        for item in result['tool_trace']: 
            print(item) 
    finally: 
        db.close() 
 
 
if __name__ == '__main__': 
    main()
