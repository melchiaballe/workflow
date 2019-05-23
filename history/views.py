from itertools import chain
from datetime import datetime, timedelta

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet
from rest_framework.generics import ListAPIView

from utils.mixins import Query, TZ, PDFHelper

from .serializers import StandupSerializer, ReportSerializer, ShortStandupProjectSerializer, BlockerSerializer, SearchSerializer
from .models import Blocker, Standup as stand_up_model

from .paginations import WeeklyReportsPagination

from accounting.models import Project



#
from accounting.serializers import ProjectSerializer
from django.contrib.postgres.search import SearchVector, SearchRank, SearchQuery
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .serializers import DoneSerializer, TodoSerializer
from .models import Done, Todo
#
class Standups(Query, ViewSet):
    """ daily standups endpoint that receives report
        from our slack workplace (SLACK API)

        *IMPORTANT: Do not ADD authentication on this
            view as it will prevent the standups from
            slack to go through.
    """
    serializer_class = StandupSerializer

    def post(self, *args, **kwargs):
        # this post method is being
        # used by slack api.
        serializer = self.serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=200)
        
    def get(self, *args, **kwargs):
        serializer = ReportSerializer(stand_up_model.objects.filter(user=self.request.user)
        , many=True)

        return Response(serializer.data, status=200)

class Standup(Query, ViewSet):
    """ daily report endpoint
    """
    serializer_class = ReportSerializer
    permission_classes = (IsAuthenticated,)

    def get(self, *args, **kwargs):
        serializer = self.serializer_class(
            self._get(self._model, **kwargs))

        return Response(serializer.data, status=200)

class StandupByWeek(Query, TZ, ListAPIView):
    """ feed endpoint.
        contains scheduled events, daily report, etc.
    """
    queryset = None
    serializer_class = ShortStandupProjectSerializer
    pagination_class = WeeklyReportsPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        # get date parameter from url
        dt_start = self.request.GET.get('date_start')
        dt_end = self.request.GET.get('date_end')
        
        start_of_week = datetime.strptime(dt_start, "%Y-%m-%d").date()
        end_of_week = ((datetime.strptime(dt_end, "%Y-%m-%d").date()) + timedelta(days=1))

        #get project id parameter from url
        project_id = self.request.GET.get('project_id')
        # get project object
        project = Project.objects.get(id=project_id)
        queryset = stand_up_model.objects.filter(date_created__range=[start_of_week, end_of_week], project=project).order_by('-date_created')
        return queryset

class ProjectBlockers(Query, ViewSet):
    serializer_class = BlockerSerializer

    def get(self, *args, **kwargs):
        project = Project.objects.get(**kwargs)
        serializer = BlockerSerializer(Blocker.objects.filter(standup__in=project.standup_set.all(), is_fixed=False), many=True)
        return Response(serializer.data, status=200)

class ProjectReport(Query, PDFHelper, ViewSet):

    def get(self, *args, **kwargs):
        dt_start = self.request.GET.get('date_start')
        dt_end = self.request.GET.get('date_end')

        start_of_week = datetime.strptime(dt_start, "%Y-%m-%d").date()
        end_of_week = ((datetime.strptime(dt_end, "%Y-%m-%d").date()) + timedelta(days=1))
        project = Project.objects.get(id=kwargs.get('id'))

        queryset = stand_up_model.objects.filter(date_created__range=[start_of_week, end_of_week], project=project).order_by('-date_created')
        serializer = ShortStandupProjectSerializer(queryset, many=True)

        #return Response(serializer.data, status=200)
        return self.produce_project_report_pdf_as_a_response(serializer.data)

class SearchAll(ListAPIView):

    queryset = None
    serializer_class = SearchSerializer
    pagination_class = WeeklyReportsPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self, *args, **kwargs):
        content = self.request.GET.get('content')
        dt_start = self.request.GET.get('date_start')
        dt_end = self.request.GET.get('date_end')
        
        if dt_start:
            start_of_week = datetime.strptime(dt_start, "%Y-%m-%d").date()
            end_of_week = ((datetime.strptime(dt_end, "%Y-%m-%d").date()) + timedelta(days=1))
            instance = sorted(chain(
               Project.objects.filter(name__icontains=content, date_created__range=[start_of_week, end_of_week]).distinct(),
                stand_up_model.objects.filter(Q(date_created__range=[start_of_week, end_of_week]), Q(done__content__icontains=content) | Q(todo__content__icontains=content) | Q(blocker__content__icontains=content)).distinct()
            ),
            key=lambda instance: instance.date_created,
            reverse=True,
        )
        else:
            instance = sorted(chain(
               Project.objects.filter(name__icontains=content).distinct(),
                stand_up_model.objects.filter(Q(done__content__icontains=content) | Q(todo__content__icontains=content) | Q(blocker__content__icontains=content)).distinct()
            ),
            key=lambda instance: instance.date_created,
            reverse=True,
        )

        return instance
        
# class SearchAll(ViewSet):

#     def get(self, *args, **kwargs):
#         #import pdb; pdb.set_trace()
#         content = self.request.GET.get('content')
        
#         # vector = SearchVector('done__content', 'todo__content', 'project__name', 'project__description')
#         # query = SearchQuery(content)
#         #test = Project.objects.annotate(search=SearchVector('name', 'description'),).filter(search=content)
#         #test = stand_up_model.objects.annotate(search=SearchVector('project__name', 'project__description'),).filter(search=content)
#         #test = stand_up_model.objects.annotate(search=SearchQuery(content))
#         #test = stand_up_model.objects.annotate(rank=SearchRank(vector, query, distinct=True)).order_by('-rank')
#         #testing =  Project.objects.filter(Q(name__icontains=content) | Q(description__icontains=content)).distinct()
#         test = sorted(chain(
#                Project.objects.filter(name__icontains=content).distinct(),
#                 stand_up_model.objects.filter(Q(done__content__icontains=content) | Q(todo__content__icontains=content) | Q(blocker__content__icontains=content)).distinct()
#             ),
#             key=lambda instance: instance.date_created,
#             reverse=True,
#         )

#         testing =  Project.objects.filter(name__icontains=content).order_by('-date_created').distinct()
#         test =  stand_up_model.objects.filter(Q(done__content__icontains=content) | Q(todo__content__icontains=content) | Q(blocker__content__icontains=content)).order_by('-date_created').distinct()
#         #test = stand_up_model.objects.filter(done__content__icontains=content) | stand_up_model.objects.filter(todo__content__icontains=content) | stand_up_model.objects.filter(blocker__content__icontains=content) 
#         serial = ProjectSerializer(testing, many=True)
#         serializer = ReportSerializer(test, many=True)
        
#         # test3 =  Blocker.objects.filter(content__icontains=content)
#         # serializer3 = BlockerSerializer(test3, many=True)
#         # test1 = Done.objects.filter(content__icontains=content)
#         # serializer1 = DoneSerializer(test1, many=True)
#         # test2 = Todo.objects.filter(content__icontains=content)
#         # serializer2 = TodoSerializer(test2, many=True)

#         dictionary = {
#             # 'expected': {
#             #     'done': serializer1.data,
#             #     'todo': serializer2.data,
#             #     'blocker': serializer3.data
#             # },
#             'projects': serial.data,
#             'standup': serializer.data
#         }
#         return Response(dictionary, status=200)