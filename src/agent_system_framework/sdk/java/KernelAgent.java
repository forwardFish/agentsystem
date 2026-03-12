package agent_system_framework.sdk.java;

public interface KernelAgent {
    String agentId();
    boolean canHandle(String taskId);
}
