from rest_framework import serializers
from .models import Project, ProjectAssignment

class ProjectAssignmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_department = serializers.CharField(source='employee.department', read_only=True)
    employee_designation = serializers.CharField(source='employee.designation', read_only=True)

    class Meta:
        model = ProjectAssignment
        fields = '__all__'
        read_only_fields = ['company', 'created_by', 'updated_by', 'created_at', 'updated_at']

    def validate(self, data):
        # Validate hours spent vs hours planned
        hours_spent = data.get('hours_spent', 0)
        hours_planned = data.get('hours_planned', 0)
        if self.instance:
            hours_spent = data.get('hours_spent', self.instance.hours_spent)
            hours_planned = data.get('hours_planned', self.instance.hours_planned)
        
        # Note: According to requirements, warn when hours spent > planned, allow override by PM.
        # Warnings are typically handled in UI. We will just allow it to save here, but 
        # frontend will show a warning if this occurs.
        return data


class ProjectSerializer(serializers.ModelSerializer):
    assignments = ProjectAssignmentSerializer(many=True, read_only=True)
    assigned_employees_count = serializers.SerializerMethodField()
    sales_person_name = serializers.CharField(source='sales_person.username', read_only=True, default='')
    project_manager_name = serializers.CharField(source='project_manager.username', read_only=True, default='')

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['company', 'created_by', 'updated_by', 'created_at', 'updated_at', 'is_deleted', 'deleted_at']

    def get_assigned_employees_count(self, obj):
        return obj.assignments.filter(assignment_status='Active').count()
