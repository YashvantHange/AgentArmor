from agentarmor.redteam.agents.attack.owasp_agent import OwaspAttackAgent

LLM01Agent = OwaspAttackAgent("llm01", ["LLM01"])
LLM02Agent = OwaspAttackAgent("llm02", ["LLM02"])
LLM03Agent = OwaspAttackAgent("llm03", ["LLM03"])
LLM04Agent = OwaspAttackAgent("llm04", ["LLM04"])
LLM05Agent = OwaspAttackAgent("llm05", ["LLM05"])
LLM06Agent = OwaspAttackAgent("llm06", ["LLM06"])
LLM07Agent = OwaspAttackAgent("llm07", ["LLM07", "LLM02"])
LLM08Agent = OwaspAttackAgent("llm08", ["LLM08", "LLM02"])
LLM09Agent = OwaspAttackAgent("llm09", ["LLM09"])
LLM10Agent = OwaspAttackAgent("llm10", ["LLM10"])
