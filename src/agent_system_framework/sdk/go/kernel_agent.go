package sdk

type KernelAgent interface {
	AgentID() string
	CanHandle(taskID string) bool
}
